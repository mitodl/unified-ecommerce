"""Routes for the system_meta app."""

from django.urls import include, re_path
from rest_framework import routers

from system_meta.views import (
    IntegratedSystemViewSet,
    ProductViewSet,
)

v0_router = routers.DefaultRouter()

v0_router.register(
    r"^meta/integrated_system",
    IntegratedSystemViewSet,
    basename="meta_integratedsystems_api",
)
v0_router.register(r"^meta/product", ProductViewSet, basename="meta_products_api")

urlpatterns = [
    re_path("^api/v0/", include((v0_router.urls, "v0"))),
]
