"""Views for the REST API for payments."""

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import mixins, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import (
    GenericViewSet,
    ViewSet,
)
from rest_framework_extensions.mixins import NestedViewSetMixin

from payments import api
from payments.models import Basket, BasketItem, Order
from payments.serializers.v0 import BasketItemSerializer, BasketSerializer
from system_meta.models import IntegratedSystem, Product

log = logging.getLogger(__name__)

# Baskets


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
def create_basket_from_product(request, system_slug, sku):
    """
    Create a new basket item from a product for the currently logged in user. Reuse
    the existing basket object if it exists.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    Args:
        system_slug (str): system slug
        sku (str): product slug

    POST Args:
        quantity (int): quantity of the product to add to the basket (defaults to 1)
        checkout (bool): redirect to checkout interstitial (defaults to False)

    Returns:
        Response: HTTP response
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request)
    quantity = request.data.get("quantity", 1)
    checkout = request.data.get("checkout", False)

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

    if checkout:
        return redirect("checkout_interstitial_page")

    return Response(
        BasketSerializer(basket).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def clear_basket(request):
    """
    Clear the basket for the current user.

    Returns:
        Response: HTTP response
    """
    basket = Basket.establish_basket(request)

    basket.delete()

    return Response(None, status=status.HTTP_204_NO_CONTENT)


# Checkout


class CheckoutApiViewSet(ViewSet):
    """Handles checkout."""

    permission_classes = (IsAuthenticated,)

    @action(
        detail=False, methods=["post"], name="Start Checkout", url_name="start_checkout"
    )
    def start_checkout(self, request):
        """
        Start the checkout process. This assembles the basket items
        into an Order with Lines for each item, applies the attached basket
        discounts, and then calls the payment gateway to prepare for payment.

        This is expected to be called from within the Ecommerce cart app, not
        from an integrated system.

        Returns:
            - JSON payload from the ol-django payment gateway app. The payment
              gateway returns data necessary to construct a form that will
              ultimately POST to the actual payment processor.
        """
        try:
            payload = api.generate_checkout_payload(request)
        except ObjectDoesNotExist:
            return Response("No basket", status=status.HTTP_406_NOT_ACCEPTABLE)

        return Response(payload)


@method_decorator(csrf_exempt, name="dispatch")
class BackofficeCallbackView(APIView):
    """
    Provides the webhook that the payment gateway uses to signal that a
    transaction's status has changed.
    """

    authentication_classes = []  # disables authentication
    permission_classes = []  # disables permission

    def post(self, request):
        """
        Handle webhook call from the payment gateway when the user has
        completed a transaction.

        Returns:
            - HTTP_200_OK if the Order is found.

        Raises:
            - Http404 if the Order is not found.
        """
        with transaction.atomic():
            order = api.get_order_from_cybersource_payment_response(request)

            # We only want to process responses related to orders which are PENDING
            # otherwise we can conclude that we already received a response through
            # the user's browser.
            if order is None:
                raise Http404
            elif order.state == Order.STATE.PENDING:
                api.process_cybersource_payment_response(request, order)

            return Response(status=status.HTTP_200_OK)
