"""Views for refund requests (api v0)."""

from drf_spectacular.utils import (
    extend_schema,
)
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from payments.models import Order
from refunds.api import create_request_from_order
from refunds.models import RequestLine
from refunds.serializers.v0 import (
    CreateFromOrderApiSerializer,
    RequestLineSerializer,
    RequestSerializer,
)


class RefundRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for refund requests."""

    serializer_class = RequestSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Return the queryset for the request - only the current user's requests."""

        if getattr(self, "swagger_fake_view", False):
            return RequestLine.objects.none()

        return self.request.user.refund_requests.all()


class RefundRequestLineViewSet(viewsets.ModelViewSet):
    """API endpoint for line items."""

    serializer_class = RequestLineSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Return the queryset for the request - only the current user's requests."""

        if getattr(self, "swagger_fake_view", False):
            return RequestLine.objects.none()

        return RequestLine.objects.filter(request__user=self.request.user).all()


@extend_schema(
    description=(
        "Create a refund from an existing order, optionally specifying which"
        " lines to refund."
    ),
    methods=["POST"],
    request=CreateFromOrderApiSerializer,
    responses={201: RequestSerializer},
)
@api_view(["POST"])
@permission_classes(
    [
        IsAuthenticated,
    ]
)
def create_from_order(request):
    """Create a refund request from an order."""

    order = Order.objects.filter(
        purchaser=request.user,
        state=Order.STATE.FULFILLED,
    ).get(pk=request.data["order"])
    lines = request.data.get("lines", [])

    new_request = create_request_from_order(request.user, order, lines=lines)

    return Response(RequestSerializer(new_request).data, status=status.HTTP_201_CREATED)
