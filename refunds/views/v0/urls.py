"""URL routing for the v0 API."""

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from refunds.views.v0 import RefundRequestLineViewSet, RefundRequestViewSet

v0_router = SimpleRouter()

v0_router.register(r"requests", RefundRequestViewSet, basename="refund-request")
v0_router.register(r"lines", RefundRequestLineViewSet, basename="refund-line")

urlpatterns = [
    path("v0", include((v0_router.urls, "refunds"), namespace="v0")),
]
