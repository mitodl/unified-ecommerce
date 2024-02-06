"""Views for the REST API for payments."""

from rest_framework import mixins, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_extensions.mixins import NestedViewSetMixin

from payments.models import Basket, BasketItem
from payments.serializers.v0 import BasketItemSerializer, BasketSerializer
from system_meta.models import IntegratedSystem, Product


class BasketViewSet(
    NestedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    """API view set for Basket"""

    serializer_class = BasketSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "user__username"
    lookup_url_kwarg = "username"

    def get_object(self):
        """
        Retrieve basket for the authenticated user.

        Returns:
            Basket: basket for the authenticated user
        """
        return Basket.objects.get(user=self.request.user)

    def get_queryset(self):
        """
        Return all baskets for the authenticated user.

        Returns:
            QuerySet: all baskets for the authenticated user
        """
        return Basket.objects.filter(user=self.request.user).all()


class BasketItemViewSet(
    NestedViewSetMixin, ListCreateAPIView, mixins.DestroyModelMixin, GenericViewSet
):
    """API view set for BasketItem"""

    serializer_class = BasketItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return all basket items for the authenticated user.

        Returns:
            QuerySet: all basket items for the authenticated user
        """
        return BasketItem.objects.filter(basket__user=self.request.user)

    def create(self, request):
        """
        Create a new basket item.

        Args:
            request (HttpRequest): HTTP request

        Returns:
            Response: HTTP response
        """
        basket = Basket.objects.get(user=request.user)
        product_id = request.data.get("product")
        serializer = self.get_serializer(
            data={"product": product_id, "basket": basket.id}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_from_product(request, system_slug, sku):
    """
    Create a new basket item from a product for the currently logged in user. Reuse
    the existing basket object if it exists.

    Args:
        system_slug (str): system slug
        sku (str): product slug

    Returns:
        Response: HTTP response
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)
    quantity = request.data.get("quantity", 1)

    try:
        product = Product.objects.get(system=system, sku=sku)
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    (_, created) = BasketItem.objects.update_or_create(
        basket=basket, product=product, defaults={"quantity": quantity}
    )
    basket.refresh_from_db()

    return Response(
        BasketSerializer(basket).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def clear(request, system_slug):
    """
    Clear the basket for the current user.

    Args:
        system_slug (str): system slug

    Returns:
        Response: HTTP response
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)

    basket.delete()

    return Response(None, status=status.HTTP_204_NO_CONTENT)
