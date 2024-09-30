"""Serializers common to the app."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        """Meta class for serializer."""

        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
