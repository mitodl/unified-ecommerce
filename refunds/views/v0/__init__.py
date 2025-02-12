"""Views for refund requests (api v0)."""

import logging

from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
)
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from payments.models import Order
from refunds.api import create_request_from_order
from refunds.exceptions import RefundAlreadyCompleteError
from refunds.models import RequestLine, RequestProcessingCode
from refunds.serializers.v0 import (
    CreateFromOrderApiSerializer,
    ProcessRequestCodeSerializer,
    RequestLineSerializer,
    RequestSerializer,
)

log = logging.getLogger(__name__)


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


@extend_schema(
    description=("Process a refund based on the code provided."),
    methods=["POST"],
    request=ProcessRequestCodeSerializer,
    responses={
        201: RequestSerializer,
        401: inline_serializer(name="ErrorSerializer", fields={"error": str}),
    },
)
@api_view(["POST"])
@permission_classes(
    [
        AllowAny,
    ]
)
def accept_code(request):
    """
    Process a request code.

    The codes themselves are sent to the request processing recipient via email,
    embedded in links to the frontend. The frontend presents the user with a
    form that requests their email address, an optional reason for refund, and
    a selector for the lines they wish to refund. This is the API that processes
    that request. (Users don't directly go to this endpoint.)

    Because this is doesn't require authentication, we send opaque messages back
    to the user. (This route will require special handling in APISIX.)
    """

    code = request.data.get("code", None)
    email = request.data.get("email", None)
    reason = request.data.get("reason", None)
    lines = request.data.get("lines", [])

    if not code or not email:
        return Response(
            {"error": "Provide a code and email."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            code = (
                RequestProcessingCode.objects.filter(
                    Q(approve_code=code) | Q(deny_code=code)
                )
                .filter(email=email)
                .filter(code_active=True)
                .get()
            )

            # If this pulled up OK, then immediately invalidate all the other
            # codes.
            RequestProcessingCode.objects.filter(
                refund_request=code.refund_request
            ).update(code_active=False)
    except RequestProcessingCode.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if code.approve_code == code:
        # do something to approve the request
        try:
            code.refund_request.approve(reason, lines=lines)
        except RefundAlreadyCompleteError as e:
            log.exception(
                "Refund failed: Attempted to accept code %s for completed request %s",
                code,
                code.refund_request,
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if code.deny_code == code:
        # do something to deny the request
        try:
            code.refund_request.approve(reason, lines=lines)
        except RefundAlreadyCompleteError as e:
            log.exception(
                "Refund failed: Attempted to accept code %s for completed request %s",
                code,
                code.refund_request,
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_200_OK)
