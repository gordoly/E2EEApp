from rest_framework import serializers
from .models import AccountUser


class UserSerialiser(serializers.ModelSerializer):
    class Meta:
        model = AccountUser
        fields = ['first_name', 'last_name', 'username', 'about', 'password', 'public_key']
        extra_kwargs = {
            'password': {'write_only': True},
            'about': {'required': False}
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)

        if password is not None:
            instance.set_password(password)

        instance.save()

        return instance