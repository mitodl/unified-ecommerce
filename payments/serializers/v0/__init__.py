"""Serializers for payments."""

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from rest_framework import serializers

from payments.models import Basket, BasketItem
from system_meta.models import Product
from system_meta.serializers import ProductSerializer
from unified_ecommerce.serializers import UserSerializer

User = get_user_model()


@dataclass
class WebhookOrder:
    """
    Webhook event data for order-based events.

    This includes order completed and order refunded states.
    """

    order: Order
    lines: Line


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
