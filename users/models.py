from django.db import models
from django.contrib.auth.models import AbstractUser


class AccountUser(AbstractUser):
    username = models.CharField(max_length=100, unique=True, primary_key=True)
    public_key = models.JSONField(null=True, blank=True)
    about = models.CharField(max_length=300, null=True, blank=True)
    
    REQUIRED_FIELDS = ['first_name', 'last_name']