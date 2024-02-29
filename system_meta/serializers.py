"""Serializers for system metadata."""

from rest_framework import serializers

from system_meta.models import IntegratedSystem, Product


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
