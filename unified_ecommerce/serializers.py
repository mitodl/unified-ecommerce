"""Serializers common to the app."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    email = serializers.SerializerMethodField()

    def get_email(self, instance) -> str | None:
        """Return the email."""
        return instance.email if not instance.is_anonymous else None

    class Meta:
        """Meta class for serializer."""

        model = User
        fields = [
            "id",
            "global_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
        ]
