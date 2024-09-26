"""Serializers for payments."""

from rest_framework import serializers

from payments.models import Basket, BasketItem, Line, Order
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

class LineSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, instance):
        product = Product.all_objects.get(
            pk=instance.product_version.field_dict["id"]
        )

        return ProductSerializer(instance=product).data

    class Meta:
        fields = [
            "quantity",
            "item_description",
            "content_type",
            "unit_price",
            "total_price",
            "id",
            "product",
        ]
        model = Line

class OrderHistorySerializer(serializers.ModelSerializer):
    titles = serializers.SerializerMethodField()
    lines = LineSerializer(many=True)

    def get_titles(self, instance):
        titles = []

        for line in instance.lines.all():
            product = Product.all_objects.get(
                pk=line.product_version.field_dict["id"]
            )
            if product.content_type.model == "courserun":
                titles.append(product.purchasable_object.course.title)
            elif product.content_type.model == "programrun":
                titles.append(product.description)
            else:
                titles.append(f"No Title - {product.id}")

        return titles

    class Meta:
        fields = [
            "id",
            "state",
            "reference_number",
            "purchaser",
            "total_price_paid",
            "lines",
            "created_on",
            "titles",
            "updated_on",
        ]
        model = Order
        depth = 1
