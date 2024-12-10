import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q
from django.utils import timezone

user_connections = {}
user_rooms = {}

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "broadcast"

        session = self.scope['session']
        
        if session.get('username'):
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            user_connections[session.get('username')] = self.channel_name
            online = list(user_connections.keys())

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast",
                    "content": online
                }
            )

            await self.accept()

        else:
            await self.close()

    async def disconnect(self, close_code):
        session = self.scope['session']

        user = session.get('username') 
        
        if user:
            if user in user_connections:
                del user_connections[user]

                if user in user_rooms:
                    del user_rooms[user]
        
                online = list(user_connections.keys())
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "broadcast",
                        "content": online
                    }
                )
                
                if self.room_group_name:
                    await self.channel_layer.group_discard(
                        self.room_group_name,
                        self.channel_name
                    )

    async def receive(self, text_data):
        from users.models import AccountUser

        message = json.loads(text_data)
        session = self.scope['session']

        if "username" in session:
            session_username = session.get("username")
            user = await self.get_user_by_username(session_username)
            
            if message["type"] == "create_room":
                receivers = message["content"]["receivers"]

                if len(receivers) == 0:
                    await self.send(text_data=json.dumps({"type": "response", "content": "no users were included in chat room creation"})) 
                    return

                if not message["content"]["room_type"]:
                    if len(receivers) != 1:
                        await self.send(text_data=json.dumps({"type": "response", "content": "there can only be one friend in a direct message chat"}))
                        return
                    
                    else:
                        try:
                            receiver = await self.get_user_by_username(receivers[0])
                            user_to_receiver = await self.filter_friend_request(user, receiver)
                            receiver_to_user = await self.filter_friend_request(receiver, user)
                            
                            if len(user_to_receiver) >= 1:
                                await self.send(text_data=json.dumps({"type": "response", "content": f"you have already sent an invite to {receivers[0]}"}))
                                return
                            
                            for request in receiver_to_user:
                                if request.status == -1:
                                    await self.send(text_data=json.dumps({"type": "response", "content": f"{receivers[0]} already sent you a friend request"}))
                                    return
                                
                            friend_room = await self.retrieve_friend_rooms(user, receiver)
                            if len(friend_room) > 0:
                                await self.send(text_data=json.dumps({"type": "response", "content": f"you are already friends with {receivers[0]}"}))
                                return
                            
                        except AccountUser.DoesNotExist:
                            await self.send(text_data=json.dumps({"type": "response", "content": f"User {receivers[0]} does not exist"}))
                            return
                        
                elif not message["content"]["group_name"]:
                    await self.send(text_data=json.dumps({"type": "response", "content": f"A group name must be provided"}))
                    return

                for username in receivers:
                    try:
                        await self.get_user_by_username(username)
                        if username == session_username:
                            await self.send(text_data=json.dumps({"type": "response", "content": "cannot have yourself as one of the invited users"}))
                            return
                    except AccountUser.DoesNotExist:
                        await self.send(text_data=json.dumps({"type": "response", "content": f"user {username} does not exist"}))
                        return
                    
                group_name = message["content"]["group_name"]
                room_type = message["content"]["room_type"]

                room = await self.create_chat_room(group_name, room_type, user)
                await self.add_member_to_room(room, user)
                
                for username in receivers:
                    receiver = await self.get_user_by_username(username)
                    created_request = await self.create_friend_request(user, receiver, room, room_type)
                    
                    if username in user_connections:
                        channel_name = user_connections.get(username)
                        if channel_name:
                            await self.channel_layer.send(
                                channel_name,
                                {
                                    "type": "new_request",
                                    "content": [session_username, created_request.id, room.pk, group_name, room_type]
                                }
                            )

                await self.send(text_data=json.dumps({"type": "response", "content": [room.pk, username, group_name, room_type]}))

            elif message["type"] == "request_res":
                new_status = message["content"]["status"]
                request_id = message["content"]["request_id"]
        
                if new_status == 0 or new_status == 1:
                    request = await self.get_friend_request(request_id)
                    receiver = await self.get_friend_request_receiver(request)
                    if receiver.username == session_username:
                        request.status = new_status
                        await self.save_friend_request(request)
                        
                        sender = await self.get_friend_request_sender(request)
                        room = await self.get_friend_request_room(request)
                        if sender.username in user_connections:
                            channel_name = user_connections.get(sender.username)
                            if channel_name:
                                await self.channel_layer.send(
                                    channel_name,
                                    {
                                        "type": "request_update",
                                        "content": [room.pk, session_username, new_status, room.name, room.type]
                                    }
                                )

                        if new_status == 1:
                            await self.add_member_to_room(room, receiver)
                            room_members = await self.get_members_of_room(room)
                            
                            if room.type:
                                for member in room_members:
                                    if member in user_rooms and member in user_connections:
                                        if user_rooms[member] == room.pk:
                                            channel_name = user_connections[member]
                                            if channel_name:
                                                await self.channel_layer.send(
                                                    channel_name,
                                                    {
                                                        "type": "update_members"
                                                    }
                                                )

            elif message["type"] == "remove_room_member":
                room_id = message["content"]["room_id"]
                room = await self.get_chat_room_by_id(room_id)
                await self.remove_member_from_room(room, user)

            elif message["type"] == "join_room":
                room_id = message["content"]["room_id"]
                room = await self.get_chat_room_by_id(int(room_id))
                members = await self.get_members_of_room(room)
                if session_username in members:
                    user_rooms[session_username] = int(room_id)

            elif message["type"] == "send_msg":
                encrypted_msg = message["content"]["message"]
                room_id = message["content"]["room_id"]
                receiver = message["content"]["receiver"]
                date_time = timezone.now().isoformat()
                
                room = await self.get_chat_room_by_id(room_id)
                members = await self.get_members_of_room(room)
                receiver_obj = await self.get_user_by_username(receiver)

                if session_username in members:
                    if receiver not in user_rooms:
                        await self.create_message(user, receiver_obj, encrypted_msg, room, date_time)
                    else:
                        if receiver in user_connections:
                            channel_name = user_connections.get(receiver)
                            if channel_name:
                                await self.channel_layer.send(
                                    channel_name,
                                    {
                                        "type": "new_msg",
                                        "content": [session_username, room_id, encrypted_msg, date_time]
                                    }
                                )

            elif message["type"] == "add_member":
                usernames_to_add = message["content"]["users_to_add"]
                room_id = message["content"]["room_id"]

                room = await self.get_chat_room_by_id(room_id)
                room_owner = await self.get_room_owner(room)

                if room_owner.username == session_username and room.type:
                    room_members = await self.get_members_of_room(room)
                    
                    for username in usernames_to_add:
                        try:
                            receiver = await self.get_user_by_username(username)
                            if username in room_members:
                                await self.send(text_data=json.dumps({"type": "response", "content": f"user {username} is already part of the group chat"}))
                                return
                        except AccountUser.DoesNotExist:
                            await self.send(text_data=json.dumps({"type": "response", "content": f"user {username} does not exist"}))
                            return
                        
                    for username in usernames_to_add:
                        receiver = await self.get_user_by_username(username)
                        created_request = await self.create_friend_request(user, receiver, room, room.type)
                        if username in user_connections:
                            channel_name = user_connections.get(username)
                            if channel_name:
                                await self.channel_layer.send(
                                    channel_name,
                                    {
                                        "type": "new_request",
                                        "content": [session_username, created_request.id, room.pk, room.name, room.type]
                                    }
                                )

            elif message["type"] == "remove_member":
                username_to_remove = message["content"]["user_to_remove"]
                room_id = message["content"]["room_id"]

                room = await self.get_chat_room_by_id(room_id)
                room_owner = await self.get_room_owner(room)

                if room_owner.username == session_username and room.type:
                    user_to_remove = await self.get_user_by_username(username_to_remove)
                    await self.remove_member_from_room(room, user_to_remove)

                    room_members = await self.get_members_of_room(room)
                    for member in room_members:
                        if member in user_rooms and member in user_connections:
                            if user_rooms[member] == room_id:
                                channel_name = user_connections[member]
                                if channel_name:
                                    await self.channel_layer.send(
                                        channel_name,
                                        {
                                            "type": "update_members"
                                        }
                                    )

    @database_sync_to_async
    def get_user_by_username(self, username):
        from users.models import AccountUser
        return AccountUser.objects.get(username=username)
    
    @database_sync_to_async
    def get_friend_request(self, pk):
        from .models import FriendRequest
        return FriendRequest.objects.get(pk=pk)
    
    @database_sync_to_async
    def get_friend_request_sender(self, friend_request):
        return friend_request.sender
    
    @database_sync_to_async
    def get_friend_request_receiver(self, friend_request):
        return friend_request.receiver
    
    @database_sync_to_async
    def get_friend_request_room(self, friend_request):
        return friend_request.room
    
    @database_sync_to_async
    def save_friend_request(self, friend_request):
        friend_request.save()
    
    @database_sync_to_async 
    def filter_friend_request(self, sender, receiver):
        from .models import FriendRequest
        return list(FriendRequest.objects.filter(sender=sender, receiver=receiver, chat_type=False))

    @database_sync_to_async 
    def retrieve_friend_rooms(self, sender, receiver):
        from .models import ChatRoom
        return list(ChatRoom.objects.filter(Q(members=sender) & Q(type=False) & Q(members=receiver)))
    
    @database_sync_to_async
    def get_chat_room_by_id(self, room_id):
        from .models import ChatRoom
        return ChatRoom.objects.get(pk=room_id)
    
    @database_sync_to_async
    def create_chat_room(self, group_name, room_type, user):
        from .models import ChatRoom
        return ChatRoom.objects.create(name=group_name, type=room_type, owner=user)
    
    @database_sync_to_async
    def create_friend_request(self, sender, receiver, room, room_type):
        from .models import FriendRequest
        return FriendRequest.objects.create(sender=sender, receiver=receiver, room=room, status=-1, chat_type=room_type)
    
    @database_sync_to_async
    def add_member_to_room(self, room, new_member):
        room.members.add(new_member)
        room.save()

    @database_sync_to_async
    def remove_member_from_room(self, room, member):
        room.members.remove(member)
        room.save()

    @database_sync_to_async
    def get_members_of_room(self, room):
        members = []
        for member in room.members.all():
            members.append(member.username)
        return members
    
    @database_sync_to_async
    def create_message(self, user, receiver, encrypted_msg, room, date_time):
        from .models import Message
        return Message.objects.create(sender=user, receiver=receiver, content=encrypted_msg, room=room, date_time=date_time)
    
    @database_sync_to_async
    def get_room_owner(self, room):
        return room.owner

    async def broadcast(self, event):
        online_users = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'broadcast',
            'content': online_users
        }))
    
    async def request_update(self, event):
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'request_update',
            'content': content
        }))

    async def new_request(self, event):
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'new_request',
            'content': content
        }))

    async def new_msg(self, event):
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'new_msg',
            'content': content
        }))

    async def update_members(self, event):
        await self.send(text_data=json.dumps({
            'type': 'update_members'
        }))