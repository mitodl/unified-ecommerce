"""Private URLs for the system_meta app."""

from django.urls import re_path

from system_meta.views import apisix_test_request

urlpatterns = [
    re_path(
        r"^apisix_test_request/$",
        apisix_test_request,
        name="apisix_test_request",
    ),
]
