"""Views for the REST API for payments."""

import logging
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_filters import rest_framework as filters
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from mitol.payment_gateway.api import PaymentGateway
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from payments import api
from payments.exceptions import ProductBlockedError
from payments.models import Basket, BasketItem, Discount, Order
from payments.permissions import HasIntegratedSystemAPIKey
from payments.serializers.v0 import (
    BasketItemSerializer,
    BasketWithProductSerializer,
    CreateBasketWithProductsSerializer,
    CyberSourceCheckoutSerializer,
    DiscountSerializer,
    OrderHistorySerializer,
)
from system_meta.models import IntegratedSystem, IntegratedSystemAPIKey, Product
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
from unified_ecommerce.plugin_manager import get_plugin_manager
from unified_ecommerce.utils import redirect_with_user_message

log = logging.getLogger(__name__)
pm = get_plugin_manager()

# Baskets


class BasketFilter(filters.FilterSet):
    """Filter class for Basket, just so we can filter by integrated system."""

    class Meta:
        """Meta class for BasketFilter"""

        model = Basket
        fields = ["integrated_system"]


@extend_schema_view(
    list=extend_schema(
        description=("Retrives the current user's baskets, one per system."),
        parameters=[
            OpenApiParameter(
                "integrated_system", OpenApiTypes.INT, OpenApiParameter.QUERY
            ),
        ],
    ),
    retrieve=extend_schema(
        description="Retrieve a basket for the current user.",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
    ),
)
class BasketViewSet(ReadOnlyModelViewSet):
    """API view set for Basket"""

    serializer_class = BasketWithProductSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.DjangoFilterBackend,)
    filterset_class = BasketFilter

    def get_queryset(self):
        """Return only baskets owned by this user."""

        if getattr(self, "swagger_fake_view", False):
            return Basket.objects.none()

        return Basket.objects.filter(user=self.request.user).all()


@extend_schema(
    description="Returns or creates a basket for the current user and system.",
    methods=["GET"],
    request=None,
    responses=BasketWithProductSerializer,
)
@api_view(["GET"])
@permission_classes((IsAuthenticated,))
def get_user_basket_for_system(request, system_slug: str):
    """
    Return the user's basket for the given system.

    Args:
        request: The request object.
        system_slug: The system slug.

    Returns:
        Basket: The basket object.
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    return Response(
        BasketWithProductSerializer(Basket.establish_basket(request, system)).data,
        status=status.HTTP_200_OK,
    )


def _create_basket_from_product(
    request, system_slug: str, sku: str, discount_code: str | None = None
):
    """
    Create a new basket item from a product for the currently logged in user. Reuse
    the existing basket object if it exists.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    If the discount code is provided, then it will be applied to the basket. If
    the discount isn't found or doesn't apply, then it will be ignored.

    Args:
        request (Request): The request object.
        system_slug (str): system slug
        sku (str): product slug
        discount_code (str): discount code
    POST Args:
        quantity (int): quantity of the product to add to the basket (defaults to 1)
        checkout (bool): redirect to checkout interstitial (defaults to False)

    Returns:
        Response: HTTP response
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)
    quantity = request.data.get("quantity", 1)
    checkout = request.data.get("checkout", False)

    try:
        product = Product.objects.get(system=system, sku=sku)
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        pm.hook.basket_add(request=request, basket=basket, basket_item=product)
    except ProductBlockedError:
        return Response(
            {"error": "Product blocked from purchasing."},
            status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
        )

    (_, created) = BasketItem.objects.update_or_create(
        basket=basket, product=product, defaults={"quantity": quantity}
    )
    auto_apply_discount_discounts = api.get_auto_apply_discounts_for_basket(basket.id)
    for discount in auto_apply_discount_discounts:
        basket.apply_discount_to_basket(discount)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            basket.apply_discount_to_basket(discount)
        except Discount.DoesNotExist:
            pass

    basket.refresh_from_db()

    if checkout:
        return redirect("checkout_interstitial_page", system_slug=system.slug)

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "system_slug", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
        OpenApiParameter("sku", OpenApiTypes.STR, OpenApiParameter.PATH, required=True),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product(request, system_slug: str, sku: str):
    """Run _create_basket_from_product."""

    return _create_basket_from_product(request, system_slug, sku)


@extend_schema(
    operation_id="create_basket_from_product_with_discount",
    description=(
        "Creates or updates a basket for the current user, "
        "adding the selected product and discount."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter(
            "system_slug", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
        OpenApiParameter("sku", OpenApiTypes.STR, OpenApiParameter.PATH, required=True),
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.PATH, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_from_product_with_discount(
    request, system_slug: str, sku: str, discount_code: str | None = None
):
    """Run _create_basket_from_product with the discount code."""

    return _create_basket_from_product(request, system_slug, sku, discount_code)


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, adding the selected product."
    ),
    methods=["POST"],
    responses=BasketWithProductSerializer,
    request=CreateBasketWithProductsSerializer,
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def create_basket_with_products(request):
    """
    Create new basket items for the currently logged in user. Reuse the existing
    basket object if it exists. Optionally apply the specified discount.

    If the checkout flag is set in the POST data, then this will create the
    basket, then immediately flip the user to the checkout interstitial (which
    then redirects to the payment gateway).

    If any of the products aren't found, this will return a 404 error. If
    the discount code is invalid, the discount won't be applied and an error
    will be logged, but the basket will still be updated.

    POST Args:
        system_slug (str): system slug
        quantity (int): quantity of the product to add to the basket (defaults to 1)
        checkout (bool): redirect to checkout interstitial (defaults to False)
        skus (list[str]): list of product SKUs to add to the basket
        discount_code (str): discount code to apply to the basket

    Returns:
        Response: HTTP response
    """
    system_slug = request.data.get("system_slug")
    checkout = request.data.get("checkout", False)
    discount_code = request.data.get("discount_code", None)
    skus = request.data.get("skus", [])

    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)
    products = []

    try:
        products = [
            (
                Product.objects.get(system=system, sku=sku["sku"]),
                sku["quantity"],
            )
            for sku in skus
        ]
    except Product.DoesNotExist:
        return Response(
            {"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        for product, quantity in products:
            pm.hook.basket_add(request=request, basket=basket, basket_item=product)
            BasketItem.objects.update_or_create(
                basket=basket, product=product, defaults={"quantity": quantity}
            )
    except ProductBlockedError:
        return Response(
            {"error": "Product blocked from purchasing.", "product": product},
            status=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS,
        )

    auto_apply_discount_discounts = api.get_auto_apply_discounts_for_basket(basket.id)
    for discount in auto_apply_discount_discounts:
        basket.apply_discount_to_basket(discount)

    if discount_code:
        try:
            discount = Discount.objects.get(discount_code=discount_code)
            basket.apply_discount_to_basket(discount)
        except Discount.DoesNotExist:
            pass

    basket.refresh_from_db()

    if checkout:
        return redirect("checkout_interstitial_page", system_slug=system.slug)

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


@extend_schema(
    description="Clears the basket for the current user.",
    methods=["DELETE"],
    versions=["v0"],
    responses=OpenApiResponse(Response(None, status=status.HTTP_204_NO_CONTENT)),
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def clear_basket(request, system_slug: str):
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


# Checkout


@extend_schema(
    description=(
        "Generates and returns the form payload for the current basket for"
        " the specified system, which can be used to start the checkout process."
    ),
    methods=["POST"],
    versions=["v0"],
    request=None,
    parameters=[
        OpenApiParameter("system_slug", OpenApiTypes.STR, OpenApiParameter.PATH),
    ],
    responses=CyberSourceCheckoutSerializer,
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def start_checkout(request, system_slug: str):
    """
    Handle checkout.

    Because of the way the payload works for CyberSource, we don't really have
    a dataclass for this. (It involves fields that have variable names - the
    line items are an array, but not.)

    The data that is returned is:
    - payload: the data that needs to be in the form (verbatim, basically)
    - url: the URL to send the form to
    - method: how to send the form (POST)

    The payload def can be found in the ol-django payment gateway app or in the
    CyberSource documentation.
    """
    try:
        system = IntegratedSystem.objects.get(slug=system_slug)
        payload = api.generate_checkout_payload(request, system)
    except ObjectDoesNotExist:
        return Response("No basket", status=status.HTTP_406_NOT_ACCEPTABLE)

    if (
        "country_blocked" in payload
        or "purchased_same_courserun" in payload
        or "purchased_non_upgradeable_courserun" in payload
        or "invalid_discounts" in payload
    ):
        return Response(payload["response"], status=status.HTTP_406_NOT_ACCEPTABLE)

    if "no_checkout" in payload:
        # The user doesn't have to check out - we're done here.
        return Response(payload, status=status.HTTP_201_CREATED)

    return Response(CyberSourceCheckoutSerializer(payload).data)


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutCallbackView(APIView):
    """
    Handles the redirect from the payment gateway after the user has completed
    checkout. This may not always happen as the redirect back to the app
    occasionally fails. If it does, then the payment gateway should trigger
    things via the backoffice webhook.
    """

    authentication_classes = []  # disables authentication
    permission_classes = [AllowAny]  # disables permission

    def _get_payment_process_redirect_url_from_line_items(self, request):
        """
        Returns the payment process redirect URL
        from the line item added most recently to the order.

        Args:
            request: Callback request from Cybersource
            after completing the payment process.

        Returns:
            URLField: The Line item's payment process
            redirect URL from the line item added most recently to the order.
        """  # noqa: D401
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

    @extend_schema(exclude=True)
    def post(self, request):
        """
        Handle successfully completed transactions.

        This does a handful of things:
        1. Verifies the incoming payload, which should be signed by the
        processor
        2. Finds and fulfills the order in the system (which should also then
        clear out the stored basket)
        3. Perform any enrollments, account status changes, etc.

        Excluded from the OpenAPI schema because it's not a public API - only
        CyberSource should be generating the payload for this request.
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

    @extend_schema(exclude=True)
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


@extend_schema_view(
    list=extend_schema(description=("Retrives the current user's completed orders.")),
    retrieve=extend_schema(
        description="Retrieve a completed order for the current user.",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
    ),
)
class OrderHistoryViewSet(ReadOnlyModelViewSet):
    """Provides APIs for displaying the users's order history."""

    serializer_class = OrderHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return the queryset for completed orders."""

        return (
            Order.objects.filter(purchaser=self.request.user)
            .filter(state__in=[Order.STATE.FULFILLED, Order.STATE.REFUNDED])
            .order_by("-created_on")
            .all()
        )


@extend_schema(
    description=(
        "Creates or updates a basket for the current user, "
        "adding the discount if valid."
    ),
    methods=["POST"],
    request=None,
    responses=BasketWithProductSerializer,
    parameters=[
        OpenApiParameter("system_slug", OpenApiTypes.STR, OpenApiParameter.PATH),
        OpenApiParameter(
            "discount_code", OpenApiTypes.STR, OpenApiParameter.QUERY, required=True
        ),
    ],
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def add_discount_to_basket(request, system_slug: str):
    """
    Add a discount to the basket for the currently logged in user.

    Args:
        system_slug (str): system slug

    POST Args:
        discount_code (str): discount code to apply to the basket

    Returns:
        Response: HTTP response
    """
    system = IntegratedSystem.objects.get(slug=system_slug)
    basket = Basket.establish_basket(request, system)
    discount_code = request.query_params.get("discount_code")

    try:
        discount = Discount.objects.get(discount_code=discount_code)
    except Discount.DoesNotExist:
        return Response(
            {"error": f"Discount '{discount_code}' not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        basket.apply_discount_to_basket(discount)
    except ValueError:
        return Response(
            {"error": "An error occurred while applying the discount."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        BasketWithProductSerializer(basket).data,
        status=status.HTTP_200_OK,
    )


class DiscountAPIViewSet(APIView):
    """
    Provides API for creating Discount objects.
    Discounts created through this API will be associated
    with the integrated system that is linked to the api key.

    Responds with a 201 status code if the discount is created successfully.
    """

    permission_classes = [HasIntegratedSystemAPIKey]
    authentication_classes = []  # disables authentication

    @extend_schema(
        description="Create a discount.",
        methods=["POST"],
        request=None,
        responses=DiscountSerializer,
    )
    def post(self, request):
        """
        Create discounts.

        Args:
            request: The request object.

        Returns:
            Response: The response object.
        """
        key = request.META["HTTP_AUTHORIZATION"].split()[1]
        api_key = IntegratedSystemAPIKey.objects.get_from_key(key)
        discount_dictionary = request.data
        discount_dictionary["integrated_system"] = str(api_key.integrated_system.id)
        discount_codes = api.generate_discount_code(
            **discount_dictionary,
        )

        return Response(
            {"discounts_created": DiscountSerializer(discount_codes, many=True).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    description="Returns the basket items for the current user.",
    methods=["GET"],
    request=None,
    responses=BasketItemSerializer,
)
class BasketItemViewSet(viewsets.ModelViewSet):
    """ViewSet for handling BasketItem operations."""

    permission_classes = (IsAuthenticated,)
    serializer_class = BasketItemSerializer

    def get_queryset(self):
        """Return only basket items owned by this user."""
        if getattr(self, "swagger_fake_view", False):
            return BasketItem.objects.none()

        return BasketItem.objects.filter(basket__user=self.request.user)
