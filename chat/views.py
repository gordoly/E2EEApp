from django.shortcuts import render
from django.http import Http404, HttpResponseForbidden, JsonResponse, HttpResponseRedirect
from django.views import View
from django.core import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import AccountUser, FriendRequest, ChatRoom, Message
from django.db.models import Q
from users.serialiser import UserSerialiser
import json


class Friends(View):
    def get(self, request):
        """
        Get request method handler for the Friends view.

        Intended for clients who are logged in and want to retrieve a webpage which
        details all the friend requests they have received, sent, and the direct message
        rooms and group chat rooms they are a part of.

        args:
            request: HttpRequest object containing the get request

        returns:
            HttpResponse: object containing the rendered friends.html template
        """
        if "username" not in request.session:
            return HttpResponseForbidden("Forbidden")
        
        user = request.session["username"]

        user_obj = AccountUser.objects.get(username=user)
        # serialise the user object into JSON to be able to pass it to the template
        user_obj_data = UserSerialiser(user_obj)

        received_requests = FriendRequest.objects.filter(receiver=user_obj)

        received_requests_list = []
        # convert the received friend request database objects into a list of dictionaries
        for received in received_requests:
            room = received.room
            received_requests_list.append({
                "id": received.pk, 
                "sender": received.sender, 
                "receiver": received.receiver, 
                "room_id": room.pk,
                "room_name": room.name,
                "room_type": received.chat_type,
                "status": received.status
            })

        sent_requests = FriendRequest.objects.filter(sender=user_obj).order_by('-pk')

        sent_requests_list = []
        # convert the sent friend request database objects into a list of dictionaries
        for sent in sent_requests:
            room = sent.room
            sent_requests_list.append({
                "id": sent.pk, 
                "sender": sent.sender, 
                "receiver": sent.receiver, 
                "room_id": room.pk,
                "room_name": room.name,
                "room_type": sent.chat_type,
                "status": sent.status
            })

        rooms = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=False))
        
        friend_rooms = []
        # convert all direct message chat rooms into a list of dictionaries
        for room in rooms:
            # display only rooms with more than one member (the only member of a chat room would be its creator)
            if room.members.count() > 1:
                room_members = room.members.all()
                # if the user is the first member of the room, display the second member's username
                if room_members[0].username == user:
                    friend = AccountUser.objects.get(username=room_members[1])
                    friend_rooms.append({"username": room_members[1], "room_id": room.id, "about": friend.about})
                else:
                    friend = AccountUser.objects.get(username=room_members[0])
                    friend_rooms.append({"username": room_members[0], "room_id": room.id, "about": friend.about})

        # serialise the group chat rooms into JSON to be able to pass it to the template
        group_chats = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=True))
        group_chat_data = json.loads(serializers.serialize('json', group_chats))

        context = {
            "received_requests": received_requests_list,
            "sent_requests": sent_requests_list,
            "group_chats": group_chat_data,
            "friends": friend_rooms,
            "user": user_obj_data.data,
        }

        return render(request, "friends.html", context)

class ChatView(View):
    def get(self, request, room_id):
        """
        Get request method handler for the Chat view.

        Intended for clients who are logged in and want to retrieve a webpage which would
        allow them to send messages and communicate with other members of a chat room.

        args:
            request: HttpRequest object containing the get request
            room_id: integer value representing the primary key of the chat room which is
            provided in the URL

        returns:
            HttpResponse: object containing the rendered chat.html template
        """
        if "username" not in request.session:
            return HttpResponseForbidden()

        # check if the room_id is an integer, and must correspond with the primary key of some
        # chat room in the database
        try:
            int(room_id)
        except ValueError:
            raise Http404
        
        user = request.session.get("username")

        user_obj = AccountUser.objects.get(username=user) 
        rooms = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=False))
        
        friend_rooms = []
        # convert all direct message chat rooms into a list of dictionaries
        for room in rooms:
            # display only rooms with more than one member (the only member of a chat room would be its creator)
            if room.members.count() > 1:
                room_members = room.members.all()
                # if the user is the first member of the room, display the second member's username
                if room_members[0].username == user:
                    friend = AccountUser.objects.get(username=room_members[1])
                    friend_rooms.append({"username": room_members[1], "room_id": room.id, "about": friend.about})
                else:
                    friend = AccountUser.objects.get(username=room_members[0])
                    friend_rooms.append({"username": room_members[0], "room_id": room.id, "about": friend.about})

        group_chats = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=True))
        # serialise the group chat rooms into JSON to be able to pass it to the template
        group_chat_data = json.loads(serializers.serialize('json', group_chats))

        room = ChatRoom.objects.get(pk=room_id)

        if user_obj in room.members.all():
            context = {
                "group_chats": group_chat_data,
                "friends": friend_rooms,
                "room_id": room_id,
                "username": user,
                "room_owner": room.owner.username,
                "room_type": room.type
            }

            return render(request, "chat.html", context)

        return HttpResponseForbidden()
   
class ChatHistoryView(View):
    def get(self, request):
        """
        Get request method handler for the ChatHistory view.

        Intended for clients who are logged in and want to retrieve the chat history of all chat rooms
        the user is part of.

        args:
            request: HttpRequest object containing the get request

        returns:
            JsonResponse: object containing the chat history of all chat rooms the user is part of
        """
        if "username" in request.session:
            user = AccountUser.objects.get(username=request.session.get("username"))
            history = Message.objects.filter(receiver=user).order_by('pk')
            
            messages = []
            for message in history:
                msg = {
                    "sender": message.sender.username, 
                    "content": message.content, 
                    "room_id": message.room.pk, 
                    "date_time": message.date_time,
                    "public_key": message.public_key,
                    "iv": message.iv
                }
                messages.append(msg)

            history.delete()

            return JsonResponse({"messages": messages})
        
        return HttpResponseForbidden()

class RoomMembersView(APIView):
    def get(self, request, room_id): 
        """
        Get request method handler for the RoomMembers view.

        Intended for clients who are logged in and want to retrieve the members of a chat room.

        args:
            request: HttpRequest object containing the get request
            room_id: integer value representing the primary key of the chat room which is
            provided in the URL

        returns:
            Response: JSON Response object containing the members of the specified chat room
        """
        if "username" in request.session:
            try:
                int(room_id)
            except ValueError:
                raise Http404
    
            room = ChatRoom.objects.get(id=room_id)
            
            room_members_data = []
            # convert all members of the chat room into a list of dictionaries
            for member in room.members.all():
                room_members_data.append({
                    "username": member.username,
                    "first_name": member.first_name,
                    "last_name": member.last_name,
                    "about": member.about if member.public_key is not None else "",
                    "public_key": member.public_key if member.public_key is not None else ""
                })

            return Response({"message": room_members_data}, status=200)
        
        return Response({"message": "Permission Denied"}, status=403)
        
class SavePublicKeyView(APIView):
    def post(self, request):
        """
        Post request method handler for the SavePublicKey view.
        
        Intended for clients who are logged in and want to save their public key to the database.

        args:
            request: HttpRequest object containing the post request

        returns:
            Response: JSON Response object containing a message indicating whether the public key was saved
            successfully or not
        """
        if "username" in request.session:
            public_key = request.data["public_key"]
            user = AccountUser.objects.get(username=request.session.get("username"))
            user.public_key = public_key;
            user.save()
            return Response({"message": "Public key saved successfully"}, status=200)
        
        return Response({"message": "Permission Denied"}, status=403)
    
class RedirectView(View):
    def get(self, request):
        """
        Get request method handler for the Redirect view.

        Args:
            request: HttpRequest object containing the get request

        Returns:
            HttpResponseRedirect: Redirects the user to the friends page if they are logged in, otherwise redirects them to the login page
        """
        if "username" in request.session:
            return HttpResponseRedirect("/friends/")
        else:
            return HttpResponseRedirect("/auth/signin/")