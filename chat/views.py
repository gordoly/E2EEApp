from django.shortcuts import render
from django.http import Http404, HttpResponseForbidden
from django.views import View
from django.core import serializers
from .models import AccountUser, FriendRequest, ChatRoom
from django.db.models import Q
from users.serialiser import UserSerialiser
import json


class Friends(View):
    def get(self, request):
        if "username" not in request.session:
            return HttpResponseForbidden("Forbidden")
        
        user = request.session["username"]

        user_obj = AccountUser.objects.get(username=user)
        user_obj_data = UserSerialiser(user_obj)

        received_requests = FriendRequest.objects.filter(receiver=user_obj)
        received_requests_data = json.loads(serializers.serialize('json', received_requests))

        sent_requests = FriendRequest.objects.filter(sender=user_obj).order_by('-pk')
        sent_requests_data = json.loads(serializers.serialize('json', sent_requests))

        rooms = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=False))
        
        friend_rooms = []
        for room in rooms:
            if room.members.count() > 1:
                room_members = room.members.all()
                
                if room_members[0].username == user:
                    friend = AccountUser.objects.get(username=room_members[1])
                    friend_rooms.append({"username": room_members[1], "room_id": room.id, "about": friend.about})
                else:
                    friend = AccountUser.objects.get(username=room_members[0])
                    friend_rooms.append({"username": room_members[0], "room_id": room.id, "about": friend.about})

        group_chats = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=True))
        group_chat_data = json.loads(serializers.serialize('json', group_chats))

        context = {
            "received_requests": received_requests_data,
            "sent_requests": sent_requests_data,
            "group_chats": group_chat_data,
            "friends": friend_rooms,
            "user": user_obj_data.data,
        }

        return render(request, "friends.html", context)

class ChatView(View):
    def get(self, request, room_id):
        if "username" not in request.session:
            return HttpResponseForbidden()

        try:
            int(room_id)
        except ValueError:
            raise Http404
        
        user = request.session.get("username")

        user_obj = AccountUser.objects.get(username=user) 
        rooms = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=False))
        
        friend_rooms = []
        for room in rooms:
            if room.members.count() > 1:
                room_members = room.members.all()
                if room_members[0].username == user:
                    friend = AccountUser.objects.get(username=room_members[1])
                    friend_rooms.append({"username": room_members[1], "room_id": room.id, "about": friend.about})
                else:
                    friend = AccountUser.objects.get(username=room_members[0])
                    friend_rooms.append({"username": room_members[0], "room_id": room.id, "about": friend.about})

        group_chats = ChatRoom.objects.filter(Q(members=user_obj) & Q(type=True))
        group_chat_data = json.loads(serializers.serialize('json', group_chats))

        if user_obj in room.members.all():
            context = {
                "group_chats": group_chat_data,
                "friends": friend_rooms,
                "room_id": room_id,
                "username": user
            }

            return render(request, "home.html", context)

        return HttpResponseForbidden()