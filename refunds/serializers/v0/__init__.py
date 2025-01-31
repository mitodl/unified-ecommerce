"""Serializers for refund requests (v0)."""

from rest_framework import serializers

from payments.serializers.v0 import OrderSerializer, TransactionSerializer
from refunds import models


class RequestLineSerializer(serializers.ModelSerializer):
    """Serializer for refund request lines."""

    transactions = TransactionSerializer(many=True)

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
