"""Serializers for system metadata."""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from reversion.models import Version

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


class WebhookProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product model for use with webhooks.

    Webhooks will need to serialize a version of a Product, so this is here to
    handle grabbing the data from a Version rather than the product itself.
    """

    sku = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    system_data = serializers.SerializerMethodField()

    def sku(self, instance):
        """Return sku from the Version field_dict."""

        return instance.field_dict["sku"]

    def name(self, instance):
        """Return name from the Version field_dict."""

        return instance.field_dict["name"]

    def price(self, instance):
        """Return price from the Version field_dict."""

        return instance.field_dict["price"]

    def description(self, instance):
        """Return description from the Version field_dict."""

        return instance.field_dict["description"]

    def system_data(self, instance):
        """Return system_data from the Version field_dict."""

        return instance.field_dict["system_data"]

    class Meta:
        """Meta class for serializer."""

        model = Version
        fields = ["sku", "name", "price", "description", "system_data"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    class Meta:
        """Meta class for serializer."""

        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
