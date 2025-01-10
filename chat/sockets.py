import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q
from django.utils import timezone

user_connections = {}
user_rooms = {}

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Method executed upon server receiving a socket connection from client.

        Adds client to the socket channel with other users, saves the socket 
        connection object, updates list of users who are currently online and 
        sends out the updated list to all socket clients.
        """
        self.room_group_name = "broadcast"

        session = self.scope['session']
        
        # check that the client has a HTTP session with the server before starting
        # a websocket connection
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
        """
        Method executed upon a client disconnecting with the socket server.

        Client's socket connection object is discarded, all clients are
        informed of the updated list of online users and client is removed
        from the socket channels.
        """
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
        """
        Method executed upon the socket server receiving a message from a client.

        The message is parsed and the appropriate action is taken based on the type
        of message received.

        All text_data is expected to be in JSON format and contain a "type" key and
        a "content" key. The "type" key is used to determine the type of message while
        the content key contains the message's content which should be appropriate for
        the message type.

        args:
            text_data (str): the message received from the client
        """
        from users.models import AccountUser
        from chat.models import ChatRoom

        message = json.loads(text_data)
        session = self.scope['session']

        if "username" in session:
            session_username = session.get("username")
            user = await self.get_user_by_username(session_username)
            
            # if the message type is create_room, a new chat room is created with the
            # creator of the chat room being added as the only member of the chat room
            if message["type"] == "create_room":
                receivers = message["content"]["receivers"]

                # prevent chat room creation if no users are included in the chat room creation
                if len(receivers) == 0:
                    await self.send(text_data=json.dumps({"type": "response", "content": "no users were included in chat room creation"})) 
                    return

                # prevent chat room creation if more than one user is included in a direct message 
                # note that a room type value of False indicates a direct message chat
                if not message["content"]["room_type"]:
                    if len(receivers) != 1:
                        await self.send(text_data=json.dumps({"type": "response", "content": "there can only be one friend in a direct message chat"}))
                        return
                    
                    else:
                        try:
                            receiver = await self.get_user_by_username(receivers[0])
                            # obtain any friend requests sent from the sender of this socket message to the intended invitee in a direct message chat
                            user_to_receiver = await self.filter_friend_request(user, receiver)
                            # obtain any friend requests sent from the intended invitee of this direct message chat to the sender of this socket message
                            receiver_to_user = await self.filter_friend_request(receiver, user)
                            
                            # prevent the creation of the direct message chat if the sender has already sent an invite to the intended invitee
                            if len(user_to_receiver) >= 1:
                                await self.send(text_data=json.dumps({"type": "response", "content": f"you have already sent an invite to {receivers[0]}"}))
                                return
                            
                            # prevent the creation of the direct message chat if the intended invitee has already sent an invite to the sender and that invite is pending
                            # note request.status == -1 indicates that the request is pending, while request.status == 0 indicates that the request was rejected and 
                            # request.status == 1 indicates that the request was accepted
                            for request in receiver_to_user:
                                if request.status == -1:
                                    await self.send(text_data=json.dumps({"type": "response", "content": f"{receivers[0]} already sent you a friend request"}))
                                    return
                            
                            # prevent the creation of the direct message chat if the sender and the intended invitee are already friends
                            friend_room = await self.retrieve_friend_rooms(user, receiver)
                            if len(friend_room) > 0:
                                await self.send(text_data=json.dumps({"type": "response", "content": f"you are already friends with {receivers[0]}"}))
                                return
                            
                        except AccountUser.DoesNotExist:
                            await self.send(text_data=json.dumps({"type": "response", "content": f"User {receivers[0]} does not exist"}))
                            return

                # prevent chat room creation if a group name is not provided for the creation of a group chat room
                elif not message["content"]["group_name"]:
                    await self.send(text_data=json.dumps({"type": "response", "content": f"A group name must be provided"}))
                    return

                # prevent chat room creation if the creator of the chat room is included in the list of invitees
                for username in receivers:
                    try:
                        await self.get_user_by_username(username)
                        if username == session_username:
                            await self.send(text_data=json.dumps({"type": "response", "content": "cannot have yourself as one of the invited users"}))
                            return
                    except AccountUser.DoesNotExist:
                        await self.send(text_data=json.dumps({"type": "response", "content": f"user {username} does not exist"}))
                        return

                # prevent chat room creation if a chat room with the provided group name already exists
                try:    
                    await self.get_chat_room_by_name(message["content"]["group_name"])
                    await self.send(text_data=json.dumps({"type": "response", "content": f"chat room with name {message['content']['group_name']} already exists"}))
                    return
                except ChatRoom.DoesNotExist:
                    pass
                    
                group_name = message["content"]["group_name"]
                room_type = message["content"]["room_type"]

                # create the chat room and add the creator of the chat room as the first member of the chat room
                room = await self.create_chat_room(group_name, room_type, user)
                await self.add_member_to_room(room, user)
                
                # send friend requests to all invitees of the chat room
                # each friend request sent to each user contains the creator of the chat room, the friend requests
                # id, the chat room id, the group name of the chat room and the room type of chat room 
                # (true = group chat, false = direct message chat)
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

                # send back to the creator of the chat room the id of the new chat room, the chat room's group name and room type
                await self.send(text_data=json.dumps({"type": "response", "content": [room.pk, username, group_name, room_type]}))
            
            # if the message type is request_res, the status of a friend request is updated
            elif message["type"] == "request_res":
                new_status = message["content"]["status"]
                request_id = message["content"]["request_id"]

                # check that the new status for a friend request is a valid value of 0 or 1
                if new_status == 0 or new_status == 1:
                    request = await self.get_friend_request(request_id)
                    receiver = await self.get_friend_request_receiver(request)
                    # ensure that the username of the sender of this socket message matches the intended username of the receiver of
                    # the friend request before updating the status of the friend request
                    if receiver.username == session_username:
                        request.status = new_status
                        await self.save_friend_request(request)
                        
                        sender = await self.get_friend_request_sender(request)
                        room = await self.get_friend_request_room(request)

                        # send the updated status of the friend request to the sender of the friend request
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

                        # if the friend request was accepted, add the invitee of the friend request to the appropriate chat room
                        if new_status == 1:
                            await self.add_member_to_room(room, receiver)
                            room_members = await self.get_members_of_room(room)
                            
                            # if the chat room type is a group chat, inform all current members of the chat room of a new group
                            # member so that each client will have an updated list of members in the group chat
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

            # if the message type is remove_room_member, remove the sender of the socket message from the provided group chat room
            elif message["type"] == "remove_room_member":
                room_id = message["content"]["room_id"]
                room = await self.get_chat_room_by_id(room_id)
                await self.remove_member_from_room(room, user)

            # if the message type is join_room, track which chat room the user joined
            elif message["type"] == "join_room":
                room_id = message["content"]["room_id"]
                room = await self.get_chat_room_by_id(int(room_id))
                members = await self.get_members_of_room(room)
                # before tracking the user as joining the provided chat room, ensure that the user is a member of the chat room first
                if session_username in members:
                    user_rooms[session_username] = int(room_id)
            
            # if the message is send_msg, send the encrypted message to the intended receiver of the message
            elif message["type"] == "send_msg":
                encrypted_msg = message["content"]["message"]
                room_id = message["content"]["room_id"]
                receiver = message["content"]["receiver"]
                iv = message["content"]["iv"]
                date_time = timezone.now().isoformat()
                
                room = await self.get_chat_room_by_id(room_id)
                members = await self.get_members_of_room(room)
                receiver_obj = await self.get_user_by_username(receiver)

                # ensure the sender of the message is a member of the chat room that they wish to send the message to
                if session_username in members:
                    # if the receiver is not online then save the message on the database
                    if receiver not in user_rooms:
                        await self.create_message(user, receiver_obj, encrypted_msg, room, date_time, iv, user.public_key)
                    # if the receiver is online then send the message directly to them
                    else:
                        if receiver in user_connections:
                            channel_name = user_connections.get(receiver)
                            if channel_name:
                                await self.channel_layer.send(
                                    channel_name,
                                    {
                                        "type": "new_msg",
                                        "content": [session_username, room_id, encrypted_msg, date_time, iv]
                                    }
                                )
            # if the message type is add_member, add the user into the group chat
            elif message["type"] == "add_member":
                usernames_to_add = message["content"]["users_to_add"]
                room_id = message["content"]["room_id"]

                room = await self.get_chat_room_by_id(room_id)
                room_owner = await self.get_room_owner(room)

                # check that the sender of the socket message is the owner of the chat room and the chat room is a group chat
                if room_owner.username == session_username and room.type:
                    room_members = await self.get_members_of_room(room)
                    
                    # add each user to the group chat room, however, check that each username is actually valid first
                    for username in usernames_to_add:
                        try:
                            receiver = await self.get_user_by_username(username)
                            if username in room_members:
                                await self.send(text_data=json.dumps({"type": "response", "content": f"user {username} is already part of the group chat"}))
                                return
                        except AccountUser.DoesNotExist:
                            await self.send(text_data=json.dumps({"type": "response", "content": f"user {username} does not exist"}))
                            return
                    
                    # add each user to the group chat room and send a friend request to each user
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

            # remove a member from a group chat room. Only the owner of the group chat room can remove members
            elif message["type"] == "remove_member":
                username_to_remove = message["content"]["user_to_remove"]
                room_id = message["content"]["room_id"]

                room = await self.get_chat_room_by_id(room_id)
                room_owner = await self.get_room_owner(room)

                # check that the sender of the socket message is the owner of the chat room and the chat room is a group chat
                if room_owner.username == session_username and room.type:
                    user_to_remove = await self.get_user_by_username(username_to_remove)
                    await self.remove_member_from_room(room, user_to_remove)

                    # inform all other members of the group chat that a member has been removed
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

            # if the message type is pk_key_change, inform all members of the chat room that the public key of the sender of the message has changed
            elif message["type"] == "pk_key_change":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "update_key",
                        "content": session_username
                    }
                )

    @database_sync_to_async
    def get_user_by_username(self, username):
        """
        Retrieve a user object from the database using the provided username.

        args:
            username (str): the username of the user to retrieve from the database

        returns:
            AccountUser: the user object retrieved from the database
        """
        from users.models import AccountUser
        return AccountUser.objects.get(username=username)
    
    @database_sync_to_async
    def get_friend_request(self, pk):
        """
        Retrieve a friend request object from the database using the provided primary key.

        args:
            pk (int): the primary key of the friend request object to retrieve from the database

        returns:
            FriendRequest: the friend request object retrieved from the database
        """
        from .models import FriendRequest
        return FriendRequest.objects.get(pk=pk)
    
    @database_sync_to_async
    def get_friend_request_sender(self, friend_request):
        """
        Retrieve the sender of a friend request object.

        args:
            friend_request (FriendRequest): the friend request object to retrieve the sender from

        returns:
            AccountUser: the sender of the friend request
        """
        return friend_request.sender
    
    @database_sync_to_async
    def get_friend_request_receiver(self, friend_request):
        """
        Retrieve the receiver of a friend request object.

        args:
            friend_request (FriendRequest): the friend request object to retrieve the receiver

        returns:
            AccountUser: the receiver of the friend request
        """
        return friend_request.receiver
    
    @database_sync_to_async
    def get_friend_request_room(self, friend_request):
        """
        Retrieve the chat room associated with a friend request object.

        args:
            friend_request (FriendRequest): the friend request object to retrieve the chat room

        returns:
            ChatRoom: the chat room associated with the friend request
        """
        return friend_request.room
    
    @database_sync_to_async
    def save_friend_request(self, friend_request):
        """
        Save a friend request object to the database.

        args:
            friend_request (FriendRequest): the friend request object to save to the database
        """
        friend_request.save()
    
    @database_sync_to_async 
    def filter_friend_request(self, sender, receiver):
        """
        Retrieve all friend requests sent from a sender to a receiver.

        args:
            sender (AccountUser): the sender of the friend request
            receiver (AccountUser): the receiver of the friend request
        """
        from .models import FriendRequest
        return list(FriendRequest.objects.filter(sender=sender, receiver=receiver, chat_type=False))

    @database_sync_to_async 
    def retrieve_friend_rooms(self, sender, receiver):
        """
        Retrieve all chat rooms that the sender and receiver are both members of.

        args:
            sender (AccountUser): the user object of the sender of some friend request
            receiver (AccountUser): the user object of the receiver of some friend request 
        """
        from .models import ChatRoom
        return list(ChatRoom.objects.filter(Q(members=sender) & Q(type=False) & Q(members=receiver)))
    
    @database_sync_to_async
    def get_chat_room_by_id(self, room_id):
        """
        Retrieve a chat room object from the database using the provided primary key.

        args:
            room_id (int): the primary key of the chat room object to retrieve from the database

        returns:
            ChatRoom: the chat room object retrieved from the database
        """
        from .models import ChatRoom
        return ChatRoom.objects.get(pk=room_id)
    
    @database_sync_to_async
    def get_chat_room_by_name(self, name):
        """
        Retrieve a chat room object from the database using the provided chat name.

        args:
            name (str): the name of the chat room used to retrieve the chat room object from the database

        returns:
            ChatRoom: the chat room object retrieved from the database
        """
        from .models import ChatRoom
        return ChatRoom.objects.get(name=name)
    
    @database_sync_to_async
    def create_chat_room(self, group_name, room_type, user):
        """
        Create a new chat room object in the database.

        args:
            group_name (str): the name of the chat room
            room_type (bool): the type of chat room (True = group chat, False = direct message chat)
            user (AccountUser): the user object of the creator of the chat room

        returns:
            ChatRoom: the chat room object created in the database
        """
        from .models import ChatRoom
        return ChatRoom.objects.create(name=group_name, type=room_type, owner=user)
    
    @database_sync_to_async
    def create_friend_request(self, sender, receiver, room, room_type):
        """
        Create a new friend request object in the database.

        args:
            sender (AccountUser): the sender of the friend request
            receiver (AccountUser): the receiver of the friend request
            room (ChatRoom): the chat room associated with the friend request
            room_type (bool): the type of chat room (True = group chat, False = direct message chat)

        returns:
            FriendRequest: the friend request object created in the database
        """
        from .models import FriendRequest
        return FriendRequest.objects.create(sender=sender, receiver=receiver, room=room, status=-1, chat_type=room_type)
    
    @database_sync_to_async
    def add_member_to_room(self, room, new_member):
        """
        Add a new member to a chat room which is stored in the database.

        args:
            room (ChatRoom): the chat room to add the new member to
            new_member (AccountUser): the new member to add to the chat room

        returns:
            ChatRoom: the chat room object with the new member added to the chat room in the database
        """
        room.members.add(new_member)
        room.save()

    @database_sync_to_async
    def remove_member_from_room(self, room, member):
        """
        Remove a member from a chat room which is stored in the database.

        args:
            room (ChatRoom): the chat room to remove the member from
            member (AccountUser): the member to remove from the chat room

        returns:
            ChatRoom: the chat room object with the member removed from the chat room in the database
        """
        room.members.remove(member)
        room.save()

    @database_sync_to_async
    def get_members_of_room(self, room):
        """
        Retrieve all members of a chat room.

        args:
            room (ChatRoom): the chat room to retrieve the members from

        returns:
            list: a list of all members of the chat room
        """
        members = []
        for member in room.members.all():
            members.append(member.username)
        return members
    
    @database_sync_to_async
    def create_message(self, user, receiver, encrypted_msg, room, date_time, iv, public_key):
        """
        Create a new message object in the database.

        args:
            user (AccountUser): the sender of the message
            receiver (AccountUser): the receiver of the message
            encrypted_msg (str): the encrypted message content
            room (ChatRoom): the chat room associated with the message
            date_time (str): the date and time the message was sent
            iv (str): the initialisation vector used to encrypt the message
            public_key (str): the public key of the sender of the message

        returns:
            Message: the message object created in the database
        """
        from .models import Message
        return Message.objects.create(sender=user, receiver=receiver, content=encrypted_msg, room=room, date_time=date_time, iv=iv, public_key=public_key)
    
    @database_sync_to_async
    def get_room_owner(self, room):
        """
        Retrieve the owner of a chat room.

        args:
            room (ChatRoom): the chat room to retrieve the owner from
        
        returns:
            AccountUser: the owner of the chat room
        """
        return room.owner

    async def broadcast(self, event):
        """
        Handler method for sending messages of the type "broadcast".
        """
        online_users = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'broadcast',
            'content': online_users
        }))
    
    async def request_update(self, event):
        """
        Handler method for sending messages of the type "request_update".
        """
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'request_update',
            'content': content
        }))

    async def new_request(self, event):
        """
        Handler method for sending messages of the type "new_request".
        """
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'new_request',
            'content': content
        }))

    async def new_msg(self, event):
        """
        Handler method for sending messages of the type "new_msg".
        """
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'new_msg',
            'content': content
        }))

    async def update_members(self, event):
        """
        Handler method for sending messages of the type "update_members".
        """
        await self.send(text_data=json.dumps({
            'type': 'update_members'
        }))

    async def update_key(self, event):
        """
        Handler method for sending messages of the type "update_key".
        """
        content = event["content"]
        await self.send(text_data=json.dumps({
            'type': 'update_key',
            'content': content
        }))