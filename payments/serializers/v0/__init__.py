"""Serializers for payments."""

from dataclasses import dataclass
from decimal import Decimal

from rest_framework import serializers

from payments.constants import PAYMENT_HOOK_ACTIONS
from payments.models import Basket, BasketItem, Line, Order
from system_meta.models import IntegratedSystem, Product
from system_meta.serializers import ProductSerializer, UserSerializer

TWO_DECIMAL_PLACES = Decimal("0.01")


@dataclass
class WebhookOrderSelector:
    """
    Class representing the order data that we into the serializer to pass to
    a webhook.

    This allows us to specify the order and the system we want to pull info for,
    so we're not leaking purchased product information to other systems.
    """

    order_id: int
    system_slug: str


class BasketItemSerializer(serializers.ModelSerializer):
    """BasketItem model serializer"""

    def perform_create(self, validated_data):
        """
        Create a BasketItem instance based on the validated data.

        Args:
            validated_data (dict): The validated data with which to create the
            BasketIteminstance.

        Returns:
            BasketItem: The created BasketItem instance.
        """
        basket = Basket.objects.get(user=validated_data["user"])
        # Product queryset returns active Products by default
        product = Product.objects.get(id=validated_data["product"])
        item, _ = BasketItem.objects.get_or_create(basket=basket, product=product)
        return item

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

    basket_items = serializers.SerializerMethodField()

    def get_basket_items(self, instance):
        """Get items in the basket"""
        return [
            BasketItemSerializer(instance=basket, context=self.context).data
            for basket in instance.basket_items.all()
        ]

    class Meta:
        """Meta options for BasketSerializer"""

        fields = [
            "id",
            "user",
            "basket_items",
        ]
        model = Basket


class BasketItemWithProductSerializer(serializers.ModelSerializer):
    """Basket item model serializer with product information"""

    product = serializers.SerializerMethodField()

    def get_product(self, instance):
        """Get the product associated with the basket item"""
        return ProductSerializer(instance=instance.product, context=self.context).data

    class Meta:
        """Meta options for BasketItemWithProductSerializer"""

        model = BasketItem
        fields = ["basket", "product", "id"]
        depth = 1


class BasketWithProductSerializer(serializers.ModelSerializer):
    """Basket model serializer with items and products"""

    basket_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    discounts = serializers.SerializerMethodField()

    def get_basket_items(self, instance):
        """Get the items in the basket"""
        return [
            BasketItemWithProductSerializer(instance=basket, context=self.context).data
            for basket in instance.basket_items.all()
        ]

    def get_total_price(self, instance):
        """Get the total price for the basket"""
        return sum(
            basket_item.base_price for basket_item in instance.basket_items.all()
        )

    class Meta:
        """Meta options for BasketWithProductSerializer"""

        fields = [
            "id",
            "user",
            "basket_items",
            "total_price",
        ]
        model = Basket


class LineSerializer(serializers.ModelSerializer):
    """Serializes a line item for an order."""

    product = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    def get_product(self, instance):
        """Get the product for the line."""
        return ProductSerializer(instance=instance.product).data

    def get_unit_price(self, instance):
        """Get the unit price for the line."""
        return str(instance.unit_price.quantize(TWO_DECIMAL_PLACES))

    def get_total_price(self, instance):
        """Get the total price for the line."""
        return str(instance.total_price.quantize(TWO_DECIMAL_PLACES))

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


class WebhookOrderDataSerializer(serializers.Serializer):
    """Serializes an Order object for use with a webhook."""

    reference_number = serializers.SerializerMethodField()
    system_slug = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    total_price_paid = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    lines = serializers.SerializerMethodField()
    key = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()

    _order = None
    _lines = None
    _action = None

    def __init__(self, *args, **kwargs):
        """Initialize the class, including pulling the order info."""
        super().__init__(*args, **kwargs)

        self._action = args[0]["action"]

        if self._action not in PAYMENT_HOOK_ACTIONS:
            value_error_str = "Invalid payment hook action: %s"
            raise ValueError(value_error_str, self._action)

        self._order = Order.objects.get(pk=args[0]["order_id"])
        # Just pull the line items for the system specified. This uses a for
        # loop because the 'product' is a virtual prop - internally the line
        # model stores a FK to the product version, not the product itself.
        self._lines = [
            line
            for line in self._order.lines.all()
            if line.product.system.slug == args[0]["system_slug"]
        ]

    def get_action(self, instance):  # noqa: ARG002
        """Get the action"""
        return self._action

    def get_key(self, instance):
        """Get the shared key for the webhook"""

        system = IntegratedSystem.objects.filter(slug=instance["system_slug"]).get()
        return system.api_key

    def get_reference_number(self, instance):  # noqa: ARG002
        """Get the reference number associated with the order"""
        return self._order.reference_number

    def get_system_slug(self, instance):
        """Get the system slug associated with the order"""
        return instance["system_slug"]

    def get_user(self, instance):  # noqa: ARG002
        """Get the purchasing user associated with the order"""
        return UserSerializer(self._order.purchaser).data

    def get_total_price_paid(self, instance):  # noqa: ARG002
        """
        Get the total price paid for the order. This includes all items on the
        order, not just the items for the specfied system.
        """
        return str(self._order.total_price_paid.quantize(TWO_DECIMAL_PLACES))

    def get_state(self, instance):  # noqa: ARG002
        """Get the state of the order."""
        return self._order.state

    def get_lines(self, instance):  # noqa: ARG002
        """Get the order's line items, for products that belong to the system."""
        return LineSerializer(self._lines, many=True).data

    class Meta:
        """Meta options for WebhookOrderDataSerializer"""

        models = WebhookOrderSelector
        fields = [
            "reference_number",
            "system_slug",
            "user",
            "total_price_paid",
            "state",
            "lines",
        ]
        read_only_fields = [
            "reference_number",
            "system_slug",
            "user",
            "total_price_paid",
            "state",
            "lines",
        ]
