"""Views for the REST API for system metadata."""

import logging

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from system_meta.api import get_product_metadata, update_product_metadata
from system_meta.models import IntegratedSystem, Product
from system_meta.serializers import (
    AdminIntegratedSystemSerializer,
    IntegratedSystemSerializer,
    ProductSerializer,
)
from unified_ecommerce.permissions import (
    IsAdminUserOrReadOnly,
)
from unified_ecommerce.utils import decode_x_header
from unified_ecommerce.viewsets import AuthVariegatedModelViewSet

log = logging.getLogger(__name__)


class IntegratedSystemViewSet(AuthVariegatedModelViewSet):
    """Viewset for IntegratedSystem model."""

    queryset = IntegratedSystem.objects.all()
    read_write_serializer_class = AdminIntegratedSystemSerializer
    read_only_serializer_class = IntegratedSystemSerializer
    permission_classes = [
        IsAdminUserOrReadOnly,
    ]


class ProductViewSet(AuthVariegatedModelViewSet):
    """Viewset for Product model."""

    queryset = Product.objects.all()
    read_write_serializer_class = ProductSerializer
    read_only_serializer_class = ProductSerializer
    filter_backends = [
        DjangoFilterBackend,
    ]
    filterset_fields = [
        "name",
        "system__slug",
    ]
    permission_classes = [
        IsAdminUserOrReadOnly,
    ]


@extend_schema(
    description=(
        "Pre-loads the product metadata for a given SKU, even if the "
        "SKU doesn't exist yet."
    ),
    methods=["GET"],
    request=None,
    responses=ProductSerializer,
)
@api_view(["GET"])
@permission_classes([])
@authentication_classes([SessionAuthentication])
@throttle_classes(
    [
        AnonRateThrottle,
    ]
)
def preload_sku(request, system_slug, sku):  # noqa: ARG001
    """
    Preload the SKU for the product.

    If we have this product, then we just return the product info (serialized
    like you'd have gotten otherwise). If we don't, we'll create a skeleton
    product, make the call to update it from Learn, and then return the new
    product.

    Integrated systems should be able to use this to ensure the resource they're
    displaying to the user has a corresponding product in UE before the user
    tries to buy it. (This of course requires that the resource has also been
    loaded into Learn too.)

    This is throttled for unauthenticated users to prevent abuse - this is
    pretty likely to spawn a request to the Learn API, so we don't want to kill
    it by accident.
    """

    if not IntegratedSystem.objects.filter(slug=system_slug).exists():
        return Response(
            {"error": "System not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    existing_product = Product.objects.filter(sku=sku, system__slug=system_slug)

    if existing_product.exists():
        return Response(ProductSerializer(existing_product.first()).data)

    product_metadata = get_product_metadata(system_slug, sku)
    if product_metadata.get("count", 0) == 0:
        return Response(
            {"error": "Resource not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    product = Product.objects.create(
        name=sku,
        sku=sku,
        description=sku,
        price=0,
        system=IntegratedSystem.objects.get(slug=system_slug),
    )
    product.save()

    update_product_metadata(product.id)
    product.refresh_from_db()

    return Response(ProductSerializer(product).data)


@api_view(["GET"])
@permission_classes([])
@authentication_classes([SessionAuthentication])
def apisix_test_request(request):
    """Test API request so we can see how the APISIX integration works."""

    response = {
        "name": "Response ok!",
        "authenticated": request.user.is_authenticated,
        "user": request.user.username if request.user is not None else None,
        "x_userinfo": decode_x_header(request, "HTTP_X_USERINFO")
        or "No HTTP_X_USERINFO header",
        "x_id_token": decode_x_header(request, "HTTP_X_ID_TOKEN")
        or "No HTTP_X_ID_TOKEN header",
    }

    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication])
def authed_traefik_test_request(request):
    """Test API request so we can see how the Traefik integration works."""

    response = {
        "name": "Response ok!",
        "user": request.user.username if request.user is not None else None,
        "metas": [f"{key}: {value}" for key, value in request.META.items()],
    }

    return Response(response, status=status.HTTP_200_OK)
