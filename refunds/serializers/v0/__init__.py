"""Serializers for refund requests (v0)."""

from rest_framework import serializers

from payments.serializers.v0 import OrderSerializer
from refunds import models


class RequestLineSerializer(serializers.ModelSerializer):
    """Serializer for refund request lines."""

    class Meta:
        """Metadata for the serializer."""

        model = models.RequestLine
        fields = "__all__"
        read_only_fields = (
            "status",
            "refund_amount",
        )


class RequestSerializer(serializers.ModelSerializer):
    """Serializer for refund requests."""

    lines = RequestLineSerializer(many=True)
    order = OrderSerializer()

    class Meta:
        """Metadata for the serializer."""

        model = models.Request
        fields = "__all__"
        read_only_fields = (
            "processed_date",
            "processed_by",
            "total_refunded",
            "status",
        )


class CreateFromOrderApiSerializer(serializers.Serializer):
    """Serializer for the create from order API."""

    order = serializers.IntegerField()
    lines = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
