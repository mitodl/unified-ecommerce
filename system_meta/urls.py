"""Routes for the system_meta app."""

from django.urls import include, re_path
from rest_framework import routers

from system_meta.views import IntegratedSystemViewSet, ProductViewSet

router = routers.DefaultRouter()

router.register(r"integrated_system", IntegratedSystemViewSet)
router.register(r"product", ProductViewSet)

urlpatterns = [re_path("^v0/", include(router.urls))]
