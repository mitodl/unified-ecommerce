"""Views for the REST API for system metadata."""

import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from system_meta.models import IntegratedSystem, Product
from system_meta.serializers import (
    AdminIntegratedSystemSerializer,
    IntegratedSystemSerializer,
    ProductSerializer,
)
from unified_ecommerce.authentication import (
    ApiGatewayAuthentication,
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
    serializer_class = ProductSerializer
    permission_classes = [
        IsAdminUserOrReadOnly,
    ]
    read_write_serializer_class = ProductSerializer
    read_only_serializer_class = ProductSerializer
    filter_backends = [
        DjangoFilterBackend,
    ]
    filterset_fields = [
        "name",
        "system__slug",
    ]


@api_view(["GET"])
@authentication_classes(
    [
        ApiGatewayAuthentication,
    ]
)
@permission_classes([])
def apisix_test_request(request):
    """Test API request so we can see how the APISIX integration works."""

    response = {
        "name": "Response ok!",
        "user": request.user.username if request.user is not None else None,
        "x_userinfo": decode_x_header(request, "HTTP_X_USERINFO")
        or "No HTTP_X_USERINFO header",
        "x_id_token": decode_x_header(request, "HTTP_X_ID_TOKEN")
        or "No HTTP_X_ID_TOKEN header",
    }

    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([])
def traefik_test_request(request):
    """Test API request so we can see how the Traefik integration works."""

    response = {
        "name": "Response ok!",
        "user": request.user.username if request.user is not None else None,
        "metas": [f"{key}: {value}" for key, value in request.META.items()],
    }

    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def authed_traefik_test_request(request):
    """Test API request so we can see how the Traefik integration works."""

    response = {
        "name": "Response ok!",
        "user": request.user.username if request.user is not None else None,
        "metas": [f"{key}: {value}" for key, value in request.META.items()],
    }

    return Response(response, status=status.HTTP_200_OK)
