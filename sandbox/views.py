"""Views for the sandbox app."""

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import status
from rest_framework.response import Response
from rest_framework.serializers import CharField, IntegerField
from rest_framework.viewsets import ViewSet

SANDBOX_SERIALIZER = inline_serializer(
    name="sandbox_values",
    fields={
        "id": IntegerField(),
        "name": CharField(),
        "age": IntegerField(),
        "email": CharField(),
    },
)


class SandboxViewSet(ViewSet):
    """
    Sandbox viewset.

    This is a simple viewset that's just here to kick the OpenAPI generation
    code into generating some new stuff, so we can trigger the formatting errors
    that I'm trying to fix.
    """

    dataset = [
        {
            "id": 1,
            "name": "Alice",
            "age": 25,
            "email": "",
        },
        {
            "id": 2,
            "name": "Bob",
            "age": 30,
            "email": "",
        },
    ]

    @extend_schema(
        description=("Retrieves the list of sandbox values."),
        methods=["GET"],
        request=None,
        responses=SANDBOX_SERIALIZER,
        operation_id="sandbox_zen_api_list",
    )
    def list(self, request):  # noqa: ARG002
        """List all items."""
        return Response(self.dataset)

    @extend_schema(
        description=("Retrieves a single sandbox value."),
        methods=["GET"],
        request=None,
        responses=SANDBOX_SERIALIZER,
        operation_id="sandbox_zen_api_retrieve",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH),
        ],
    )
    def retrieve(self, request, id: int):  # noqa: A002, ARG002
        """Retrieve a single item."""
        try:
            item = next(item for item in self.dataset if item["id"] == int(id))
        except StopIteration:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(item)
