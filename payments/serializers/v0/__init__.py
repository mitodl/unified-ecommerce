"""Serializers for payments."""

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_dataclasses.serializers import DataclassSerializer

from payments.constants import (
    PAYMENT_HOOK_ACTION_POST_SALE,
    PAYMENT_HOOK_ACTIONS,
)
from payments.models import Basket, BasketItem, Line, Order
from system_meta.models import Product
from system_meta.serializers import IntegratedSystemSerializer, ProductSerializer
from unified_ecommerce.serializers import UserSerializer

User = get_user_model()


@dataclass
class WebhookOrder:
    """
    Webhook event data for order-based events.

    This includes order completed and order refunded states.
    """

    order: Order
    lines: list[Line]


@dataclass
class WebhookCart:
    """
    Webhook event data for cart-based events.

    This includes item added to cart and item removed from cart. (These are so
    the integrated system can fire off enrollments when people add things to
    their cart - MITx Online specifically enrolls as soon as you add to cart,
    regardless of whether or not you pay, and then upgrades when you do, for
    instance.)
    """

    product: Product


@dataclass
class WebhookBase:
    """Class representing the base data that we need to post a webhook."""

    system_key: str
    type: str
    user: object
    data: WebhookOrder | WebhookCart


class BasketItemSerializer(serializers.ModelSerializer):
    """BasketItem model serializer"""

    class Meta:
        """Meta options for BasketItemSerializer"""

        model = BasketItem
        fields = [
            "basket",
            "product",
            "id",
        ]


class BasketSerializer(serializers.ModelSerializer):
    """Basket model serializer"""

    basket_items = BasketItemSerializer(many=True)
    integrated_system = IntegratedSystemSerializer()

    class Meta:
        """Meta options for BasketSerializer"""

        fields = [
            "id",
            "user",
            "integrated_system",
            "basket_items",
        ]
        model = Basket


class BasketItemWithProductSerializer(serializers.ModelSerializer):
    """Basket item model serializer with product information"""

    product = ProductSerializer()

    class Meta:
        """Meta options for BasketItemWithProductSerializer"""

        model = BasketItem
        fields = ["basket", "product", "id", "price", "discounted_price"]
        depth = 1


class BasketWithProductSerializer(serializers.ModelSerializer):
    """Basket model serializer with items and products"""

    basket_items = BasketItemWithProductSerializer(many=True)
    total_price = serializers.SerializerMethodField()
    integrated_system = IntegratedSystemSerializer()

    def get_total_price(self, instance) -> Decimal:
        """Get the total price for the basket"""
        return sum(
            basket_item.base_price for basket_item in instance.basket_items.all()
        )

    class Meta:
        """Meta options for BasketWithProductSerializer"""

        fields = [
            "id",
            "user",
            "integrated_system",
            "basket_items",
            "total_price",
        ]
        model = Basket


class LineSerializer(serializers.ModelSerializer):
    """Serializes a line item for an order."""

    product = ProductSerializer()
    unit_price = serializers.DecimalField(max_digits=9, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=9, decimal_places=2)

    class Meta:
        """Meta options for LineSerializer"""

        fields = [
            "id",
            "quantity",
            "item_description",
            "unit_price",
            "total_price",
            "product",
        ]
        model = Line


class WebhookOrderDataSerializer(DataclassSerializer):
    """Serializes order data for submission to the webhook."""

    reference_number = serializers.CharField(source="order.reference_number")
    total_price_paid = serializers.DecimalField(
        source="order.total_price_paid", max_digits=9, decimal_places=2
    )
    state = serializers.CharField(source="order.state")
    lines = LineSerializer(many=True)

    class Meta:
        """Meta options for WebhookOrderDataSerializer"""

        dataclass = WebhookOrder


class WebhookBaseSerializer(DataclassSerializer):
    """Base serializer for webhooks."""

    system_key = serializers.CharField()
    type = serializers.ChoiceField(choices=PAYMENT_HOOK_ACTIONS)
    user = UserSerializer()
    data = serializers.SerializerMethodField()

    def get_data(self, instance):
        """Resolve and return the proper serializer for the data field."""

        if instance.type == PAYMENT_HOOK_ACTION_POST_SALE:
            return WebhookOrderDataSerializer(instance.data).data

        error_msg = "Invalid webhook type %s"
        raise ValueError(error_msg, instance.type)

    class Meta:
        """Meta options for WebhookBaseSerializer"""

        dataclass = WebhookBase
        model = Line


class OrderHistorySerializer(serializers.ModelSerializer):
    """Serializer for order history."""

    lines = LineSerializer(many=True)

    class Meta:
        """Meta options for OrderHistorySerializer"""

        fields = [
            "id",
            "state",
            "reference_number",
            "purchaser",
            "total_price_paid",
            "lines",
            "created_on",
            "updated_on",
        ]
        model = Order
