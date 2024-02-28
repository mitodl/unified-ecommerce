"""Views for the REST API for system metadata."""

import base64
import json
import logging

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
from system_meta.serializers import IntegratedSystemSerializer, ProductSerializer
from unified_ecommerce.authentication import (
    ApiGatewayAuthentication,
)

log = logging.getLogger(__name__)


class IntegratedSystemViewSet(viewsets.ModelViewSet):
    """Viewset for IntegratedSystem model."""

    queryset = IntegratedSystem.objects.all()
    serializer_class = IntegratedSystemSerializer
    permission_classes = (IsAuthenticated,)


class ProductViewSet(viewsets.ModelViewSet):
    """Viewset for Product model."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated,)


@api_view(["GET"])
@authentication_classes(
    [
        ApiGatewayAuthentication,
    ]
)
@permission_classes([])
def apisix_test_request(request):
    """Test API request so we can see how the APISIX integration works."""

    def decode_x_header(header):
        x_userinfo = request.META.get(header, False)

        if not x_userinfo:
            return f"No {header} header"

        decoded_x_userinfo = base64.b64decode(x_userinfo)
        return json.loads(decoded_x_userinfo)

    response = {
        "name": "Response ok!",
        "user": request.user.username if request.user is not None else None,
        "x_userinfo": decode_x_header("HTTP_X_USERINFO"),
        "x_id_token": decode_x_header("HTTP_X_ID_TOKEN"),
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
