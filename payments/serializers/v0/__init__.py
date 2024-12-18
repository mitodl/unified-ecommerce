"""Serializers for payments."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_dataclasses.serializers import DataclassSerializer

from payments.constants import (
    PAYMENT_HOOK_ACTION_POST_SALE,
    PAYMENT_HOOK_ACTION_PRE_SALE,
    PAYMENT_HOOK_ACTION_TEST,
    PAYMENT_HOOK_ACTIONS,
)
from payments.models import Basket, BasketItem, Company, Discount, Line, Order, TaxRate
from system_meta.models import Product
from system_meta.serializers import IntegratedSystemSerializer, ProductSerializer
from unified_ecommerce.serializers import UserSerializer

User = get_user_model()


class WebhookBasketAction(Enum):
    """Enum for basket actions."""

    ADD = "add"
    REMOVE = "remove"


@dataclass
class WebhookOrder:
    """
    Webhook event data for order-based events.

    This includes order completed and order refunded states.
    """

    order: Order
    lines: list[Line]

    def __str__(self):
        """Return a resonable string representation of the object."""
        return f"order {self.order.reference_number}"


@dataclass
class WebhookBasket:
    """
    Webhook event data for basket-based events.

    This includes item added to cart and item removed from cart. (These are so
    the integrated system can fire off enrollments when people add things to
    their cart - MITx Online specifically enrolls as soon as you add to cart,
    regardless of whether or not you pay, and then upgrades when you do, for
    instance.)
    """

    product: Product
    action: WebhookBasketAction

    def __str__(self):
        """Return a resonable string representation of the object."""
        return f"cart {self.action.value} event for {self.product}"


@dataclass
class WebhookTest:
    """Test dataclass for WebhookBase."""

    some_data: str

    def __str__(self):
        """Return a resonable string representation of the object."""
        return f"test data: {self.some_data}"


@dataclass
class WebhookBase:
    """Class representing the base data that we need to post a webhook."""

    system_slug: str
    system_key: str
    type: str
    user: object
    data: WebhookOrder | WebhookBasket | WebhookTest

    def __str__(self):
        """Return a resonable string representation of the object."""
        return f"{self.type} for {self.user} in {self.system_slug}: {self.data}"


class TaxRateSerializer(serializers.ModelSerializer):
    """TaxRate model serializer"""

    class Meta:
        """Meta options for TaxRateSerializer"""

        model = TaxRate
        fields = ["id", "country_code", "tax_rate", "tax_rate_name"]


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for companies."""

    class Meta:
        """Meta options for CompanySerializer"""

        model = Company
        fields = ["id", "name"]


class SimpleDiscountSerializer(serializers.ModelSerializer):
    """Simpler serializer for discounts."""

    class Meta:
        """Meta options for SimpleDiscountSerializer"""

        model = Discount
        fields = [
            "id",
            "discount_code",
            "amount",
            "discount_type",
            "formatted_discount_amount",
        ]


class DiscountSerializer(SimpleDiscountSerializer):
    """Serializer for discounts."""

    assigned_users = UserSerializer(many=True)
    integrated_system = IntegratedSystemSerializer()
    product = ProductSerializer()
    company = CompanySerializer()

    class Meta:
        """Meta options for DiscountSerializer"""

        fields = [
            "id",
            "discount_code",
            "amount",
            "payment_type",
            "max_redemptions",
            "activation_date",
            "expiration_date",
            "integrated_system",
            "product",
            "assigned_users",
            "company",
        ]
        model = Discount


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
    discount_applied = serializers.SerializerMethodField()

    @extend_schema_field(SimpleDiscountSerializer)
    def get_discount_applied(self, instance):
        """Return "best_discount_for_item_from_basket"."""

        return SimpleDiscountSerializer(
            instance.best_discount_for_item_from_basket
        ).data

    class Meta:
        """Meta options for BasketItemWithProductSerializer"""

        model = BasketItem
        fields = [
            "product",
            "id",
            "price",
            "discounted_price",
            "quantity",
            "discount_applied",
        ]
        depth = 1


class BasketWithProductSerializer(serializers.ModelSerializer):
    """Basket model serializer with items and products"""

    basket_items = BasketItemWithProductSerializer(many=True)
    total_price = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    integrated_system = IntegratedSystemSerializer()
    tax_rate = TaxRateSerializer()

    def get_total_price(self, instance) -> Decimal:
        """Get the total price for the basket"""
        return instance.total_money

    def get_tax(self, instance) -> Decimal:
        """Get the tax for the basket"""
        return instance.tax_money

    def get_subtotal(self, instance) -> Decimal:
        """Get the subtotal for the basket"""
        return instance.subtotal_money

    class Meta:
        """Meta options for BasketWithProductSerializer"""

        fields = [
            "id",
            "user",
            "integrated_system",
            "basket_items",
            "subtotal",
            "tax",
            "tax_rate",
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


class WebhookBasketDataSerializer(DataclassSerializer):
    """Serializes order data for submission to the webhook."""

    product = ProductSerializer()
    action = serializers.SerializerMethodField()

    def get_action(self, instance):
        """Return the action as a string."""
        return instance.action.value

    class Meta:
        """Meta options for WebhookBasketDataSerializer"""

        dataclass = WebhookBasket


class WebhookTestDataSerializer(DataclassSerializer):
    """Serializes test data for submission to the webhook."""

    some_data = serializers.CharField()

    class Meta:
        """Meta options for WebhookTestDataSerializer"""

        dataclass = WebhookTest


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
        elif instance.type == PAYMENT_HOOK_ACTION_PRE_SALE:
            return WebhookBasketDataSerializer(instance.data).data
        elif instance.type == PAYMENT_HOOK_ACTION_TEST:
            return WebhookTestDataSerializer(instance.data).data

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


class CyberSourceCheckoutSerializer(serializers.Serializer):
    """Really basic serializer for the payload that we need to send to CyberSource."""

    payload = serializers.DictField()
    url = serializers.CharField()
    method = serializers.CharField()
