"""Serializers for payments."""

from rest_framework import serializers

from payments.models import Basket, BasketItem
from system_meta.models import Product
from system_meta.serializers import ProductSerializer


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