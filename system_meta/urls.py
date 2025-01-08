"""Routes for the system_meta app."""

from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework import routers

from system_meta.views import (
    IntegratedSystemViewSet,
    ProductViewSet,
    preload_sku,
)

v0_router = routers.DefaultRouter()

v0_router.register(
    r"^meta/integrated_system",
    IntegratedSystemViewSet,
    basename="meta_integratedsystems_api",
)
v0_router.register(r"^meta/product", ProductViewSet, basename="meta_products_api")

app_name = "v0"
urlpatterns = [
    path("admin/", admin.site.urls),
    re_path(
        r"^api/v0/meta/product/preload/(?P<system_slug>[^/]+)/(?P<sku>[^/]+)/$",
        preload_sku,
    ),
    re_path("^api/v0/", include((v0_router.urls, "v0"))),
]
