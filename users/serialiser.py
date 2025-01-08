from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from rest_framework import serializers
from .models import AccountUser
from .validator import ExtraPasswordValidator


class UserSerialiser(serializers.ModelSerializer):
    class Meta:
        model = AccountUser
        fields = ['first_name', 'last_name', 'username', 'about', 'password', 'public_key']
        extra_kwargs = {
            'password': {'write_only': True},
            'about': {'required': False},
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate_password(self, value):
        """
        Validates the password using Django's default password validation
        and a custom password validator.

        Args:
            value (str): The password to validate.
        
        Returns:
            str: The password if it is valid.
        """
        try:
            password_validation.validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e)[0])
        
        custom_validator = ExtraPasswordValidator()
        try:
            custom_validator.validate(value)
        except ValidationError as e:
            raise serializers.ValidationError(list(e)[0])

        return value

    def create(self, validated_data):
        """
        Create a new user instance in the database with the validated data, but
        first hashes the password before saving it in the user object on the database.

        Args:
            validated_data (dict): The validated data from the request.

        Returns:
            AccountUser: The user object that was created.
        """
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)

        if password is not None:
            instance.set_password(password)

        instance.save()

        return instance