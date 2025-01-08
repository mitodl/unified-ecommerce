"""Private URLs for the system_meta app."""

from django.urls import re_path

from system_meta.views import (
    apisix_test_request,
    authed_traefik_test_request,
)

urlpatterns = [
    re_path(
        r"^apisix_test_request/$",
        apisix_test_request,
        name="apisix_test_request",
    ),
    re_path(
        r"^authed_traefik_test_request/$",
        authed_traefik_test_request,
        name="authed_traefik_test_request",
    ),
]
