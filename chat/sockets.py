import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q

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
                        
                else:
                    if not message["content"]["group_name"]:
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

    @database_sync_to_async
    def get_user_by_username(self, username):
        from users.models import AccountUser
        return AccountUser.objects.get(username=username)
    
    @database_sync_to_async 
    def filter_friend_request(self, sender, receiver):
        from .models import FriendRequest
        return list(FriendRequest.objects.filter(sender=sender, receiver=receiver, chat_type=False))

    @database_sync_to_async 
    def retrieve_friend_rooms(self, sender, receiver):
        from .models import ChatRoom
        return list(ChatRoom.objects.filter(Q(members=sender) & Q(type=False) & Q(members=receiver)))
    
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

    async def broadcast(self, event):
        online_users = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'broadcast',
            'content': online_users
        }))

    async def new_request(self, event):
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'new_request',
            'content': content
        }))