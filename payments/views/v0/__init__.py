"""Views for the REST API for payments."""

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from mitol.payment_gateway.api import PaymentGateway
from rest_framework import mixins, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import (
    GenericViewSet,
    ReadOnlyModelViewSet,
    ViewSet,
)
from rest_framework_extensions.mixins import NestedViewSetMixin

from payments import api
from payments.models import Basket, BasketItem, Order
from payments.serializers.v0 import (
    BasketItemSerializer,
    BasketSerializer,
    OrderHistorySerializer,
)
from system_meta.models import IntegratedSystem, Product
from unified_ecommerce import settings
from unified_ecommerce.constants import (
    POST_SALE_SOURCE_BACKOFFICE,
    POST_SALE_SOURCE_REDIRECT,
    USER_MSG_TYPE_PAYMENT_ACCEPTED,
    USER_MSG_TYPE_PAYMENT_CANCELLED,
    USER_MSG_TYPE_PAYMENT_DECLINED,
    USER_MSG_TYPE_PAYMENT_ERROR,
    USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN,
)
from unified_ecommerce.utils import redirect_with_user_message

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

        if (
            "country_blocked" in payload
            or "no_checkout" in payload
            or "purchased_same_courserun" in payload
            or "purchased_non_upgradeable_courserun" in payload
            or "invalid_discounts" in payload
        ):
            return payload["response"]

        return Response(payload)


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutCallbackView(View):
    """
    Handles the redirect from the payment gateway after the user has completed
    checkout. This may not always happen as the redirect back to the app
    occasionally fails. If it does, then the payment gateway should trigger
    things via the backoffice webhook.
    """

    def _get_payment_process_redirect_url_from_line_items(self, request):
        """
        Returns the payment process redirect URL from the line item added most recently to the order.

        Args:
            request: Callback request from Cybersource after completing the payment process.

        Returns:
            URLField: The Line item's payment process redirect URL from the line item added most recently to the order.
        """
        order = api.get_order_from_cybersource_payment_response(request)
        return order.lines.last().product.system.payment_process_redirect_url

    def post_checkout_redirect(self, order_state, request):
        """
        Redirect the user with a message depending on the provided state.

        Args:
            - order_state (str): the order state to consider
            - order (Order): the order itself
            - request (HttpRequest): the request

        Returns: HttpResponse
        """
        if order_state == Order.STATE.CANCELED:
            return redirect_with_user_message(
                self._get_payment_process_redirect_url_from_line_items(request),
                {"type": USER_MSG_TYPE_PAYMENT_CANCELLED},
            )
        elif order_state == Order.STATE.ERRORED:
            return redirect_with_user_message(
                self._get_payment_process_redirect_url_from_line_items(request),
                {"type": USER_MSG_TYPE_PAYMENT_ERROR},
            )
        elif order_state == Order.STATE.DECLINED:
            return redirect_with_user_message(
                self._get_payment_process_redirect_url_from_line_items(request),
                {"type": USER_MSG_TYPE_PAYMENT_DECLINED},
            )
        elif order_state == Order.STATE.FULFILLED:
            return redirect_with_user_message(
                self._get_payment_process_redirect_url_from_line_items(request),
                {
                    "type": USER_MSG_TYPE_PAYMENT_ACCEPTED,
                },
            )
        else:
            if not PaymentGateway.validate_processor_response(
                settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
            ):
                log.info("Could not validate payment response for order")
            else:
                processor_response = PaymentGateway.get_formatted_response(
                    settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
                )
            log.error(
                (
                    "Checkout callback unknown error for transaction_id %s, state"
                    " %s, reason_code %s, message %s, and ProcessorResponse %s"
                ),
                processor_response.transaction_id,
                order_state,
                processor_response.response_code,
                processor_response.message,
                processor_response,
            )
            return redirect_with_user_message(
                self._get_payment_process_redirect_url_from_line_items(request),
                {"type": USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN},
            )

    def post(self, request):
        """
        Handle successfully completed transactions.

        This does a handful of things:
        1. Verifies the incoming payload, which should be signed by the
        processor
        2. Finds and fulfills the order in the system (which should also then
        clear out the stored basket)
        3. Perform any enrollments, account status changes, etc.
        """

        with transaction.atomic():
            order = api.get_order_from_cybersource_payment_response(request)
            if order is None:
                return HttpResponse("Order not found")

            # Only process the response if the database record in pending status
            # If it is, then we can process the response as per usual.
            # If it isn't, then we just need to redirect the user with the
            # proper message.

            if order.state == Order.STATE.PENDING:
                processed_order_state = api.process_cybersource_payment_response(
                    request,
                    order,
                    POST_SALE_SOURCE_REDIRECT,
                )

                return self.post_checkout_redirect(processed_order_state, request)
            else:
                return self.post_checkout_redirect(order.state, request)


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
                api.process_cybersource_payment_response(
                    request, order, POST_SALE_SOURCE_BACKOFFICE
                )

            return Response(status=status.HTTP_200_OK)


class OrderHistoryViewSet(ReadOnlyModelViewSet):
    serializer_class = OrderHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(purchaser=self.request.user)
            .filter(state__in=[Order.STATE.FULFILLED, Order.STATE.REFUNDED])
            .order_by("-created_on")
            .all()
        )
