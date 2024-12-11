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
        if "username" not in request.session:
            return HttpResponseForbidden("Forbidden")
        
        user = request.session["username"]

        user_obj = AccountUser.objects.get(username=user)
        user_obj_data = UserSerialiser(user_obj)

        received_requests = FriendRequest.objects.filter(receiver=user_obj)

        received_requests_list = []
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
            "received_requests": received_requests_list,
            "sent_requests": sent_requests_list,
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
                    "hash": message.hash_digest,
                    "salt": message.salt
                }
                messages.append(msg)

            history.delete()

            return JsonResponse({"messages": messages})
        
        return HttpResponseForbidden()

class RoomMembersView(APIView):
    def get(self, request, room_id): 
        if "username" in request.session:
            try:
                int(room_id)
            except ValueError:
                raise Http404
    
            room = ChatRoom.objects.get(id=room_id)
            
            room_members_data = []
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
        if "username" in request.session:
            public_key = request.data["public_key"]
            user = AccountUser.objects.get(username=request.session.get("username"))
            user.public_key = public_key;
            user.save()
            return Response({"message": "Public key saved successfully"}, status=200)
        
        return Response({"message": "Permission Denied"}, status=403)
    
class RedirectView(View):
    def get(self, request):
        if "username" in request.session:
            return HttpResponseRedirect("/friends/")
        else:
            return HttpResponseRedirect("/auth/signin/")