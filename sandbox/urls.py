"""Routes for the sandbox app."""

from django.urls import include, re_path
from rest_framework import routers

from sandbox.views import SandboxViewSet, return_nothing

v0_router = routers.DefaultRouter()

v0_router.register(
    r"^sandbox/zen",
    SandboxViewSet,
    basename="sandbox_zen_api",
)

app_name = "v0"
urlpatterns = [
    re_path("^api/v0/", include((v0_router.urls, "v0"))),
    re_path("^api/v0/sandbox/return_nothing", return_nothing),
]
