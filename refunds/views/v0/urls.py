"""URL routing for the v0 API."""

from django.urls import include, re_path
from rest_framework.routers import SimpleRouter

from refunds.views.v0 import (
    RefundRequestLineViewSet,
    RefundRequestViewSet,
    create_from_order,
)

v0_router = SimpleRouter()

v0_router.register(r"requests", RefundRequestViewSet, basename="refund-request")
v0_router.register(r"lines", RefundRequestLineViewSet, basename="refund-line")

urlpatterns = [
    re_path(r"^", include(v0_router.urls)),
    re_path("^create_from_order", create_from_order),
]
