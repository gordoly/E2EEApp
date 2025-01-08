from django.db import models
from users.models import AccountUser

class RoomMember(models.Model):
    chat_room = models.ForeignKey('ChatRoom', on_delete=models.CASCADE)
    user = models.ForeignKey(AccountUser, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['chat_room', 'user']

class ChatRoom(models.Model):
    name = models.CharField(max_length=100)
    # type = True if the chat room is a group chat, False if it is a direct message chat
    type = models.BooleanField()
    owner = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name='owned_rooms')
    members = models.ManyToManyField(AccountUser, through='RoomMember')

class FriendRequest(models.Model):
    class Status(models.IntegerChoices):
        PENDING = -1, 'Pending'
        ACCEPTED = 2, 'Accepted'
        DECLINED = 3, 'Declined'

    sender = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name="request_sender")
    receiver = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name="request_receiver")
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    # the status of the friend request, -1 for pending, 1 for accepted, 0 for declined
    status = models.IntegerField(choices=Status.choices)
    # type = True if the chat room referenced is a group chat, False if it is a direct message chat
    chat_type = models.BooleanField()

class Message(models.Model):
    sender = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name="sender")
    receiver = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name="receiver") 
    content = models.TextField()
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    # The date and time the message was received by the server
    date_time = models.DateTimeField()
    # Sender's public key used for deriving the Diffie-Hellman shared key used for encrypting this message
    public_key = models.JSONField()
    # Initialization Vector used for encrypting this message
    iv = models.TextField()