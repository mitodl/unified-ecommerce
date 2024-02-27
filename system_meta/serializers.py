"""Serializers for system metadata."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from system_meta.models import IntegratedSystem, Product

User = get_user_model()


class IntegratedSystemSerializer(serializers.ModelSerializer):
    """Serializer for IntegratedSystem model."""

    class Meta:
        """Meta class for serializer."""

        model = IntegratedSystem
        fields = ["id", "name", "slug", "description"]


class AdminIntegratedSystemSerializer(serializers.ModelSerializer):
    """Serializer for IntegratedSystem model."""

    class Meta:
        """Meta class for serializer."""

        model = IntegratedSystem
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model."""

    class Meta:
        """Meta class for serializer."""

        model = Product
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        """Meta class for serializer."""

        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
