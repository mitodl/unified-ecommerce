"""Serializers for payments."""

from dataclasses import dataclass

from rest_framework import serializers

from payments.models import Basket, BasketItem, Order
from system_meta.models import Product
from system_meta.serializers import ProductSerializer


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


class WebhookOrderDataSerializer(serializers.Serializer):
    """Serializes an Order object for use with a webhook."""

    reference_number = serializers.SerializerMethodField()
    system_slug = serializers.SerializerMethodField()
    user = serializers.SerialzerMethodField()
    total_price_paid = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    lines = serializers.SerializerMethodField()

    _order = None

    def __init__(self, *args, **kwargs):
        """Initialize the class, including pulling the order info."""
        super().__init__(*args, **kwargs)

        self._order = Order.objects.prefetch("lines", "lines__product_version").get(
            pk=self.context["order_id"]
        )

    def get_system_slug(self, instance):
        """Get the system slug associated with the order"""
        return instance.system.slug

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
