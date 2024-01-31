"""Routes for the system_meta app."""

from django.urls import include, re_path
from rest_framework import routers

from system_meta.views import (
    IntegratedSystemViewSet,
    ProductViewSet,
    apisix_test_request,
    traefik_test_request,
)

router = routers.DefaultRouter()

router.register(r"integrated_system", IntegratedSystemViewSet)
router.register(r"product", ProductViewSet)

urlpatterns = [
    re_path("^", include(router.urls)),
    re_path(
        r"^apisix_test_request/$",
        apisix_test_request,
        name="apisix_test_request",
    ),
    re_path(
        r"^traefik_test_request/$",
        traefik_test_request,
        name="traefik_test_request",
    ),
]
