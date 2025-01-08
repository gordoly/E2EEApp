from django.db import models
from django.contrib.auth.models import AbstractUser


class AccountUser(AbstractUser):
    username = models.CharField(max_length=100, unique=True, primary_key=True)
    first_name = models.CharField(max_length=100, null=False, blank=False)
    last_name = models.CharField(max_length=100, null=False, blank=False)
    # user's public key which will be used by itself and other users to derive a Diffie-Hellman shared secret
    public_key = models.JSONField(null=True, blank=True)
    about = models.CharField(max_length=300, null=True, blank=True)
    
    REQUIRED_FIELDS = ['first_name', 'last_name']