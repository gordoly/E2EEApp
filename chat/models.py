from django.db import models
from users.models import AccountUser

class RoomMember(models.Model):
    chat_room = models.ForeignKey('ChatRoom', on_delete=models.CASCADE)
    user = models.ForeignKey(AccountUser, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['chat_room', 'user']

class ChatRoom(models.Model):
    name = models.CharField(max_length=100)
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
    status = models.IntegerField(choices=Status.choices)
    chat_type = models.BooleanField()

class Message(models.Model):
    sender = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name="sender")
    receiver = models.ForeignKey(AccountUser, on_delete=models.CASCADE, related_name="receiver") 
    content = models.TextField()
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE)
    date_time = models.DateTimeField()
    public_key = models.JSONField()
    iv = models.TextField()