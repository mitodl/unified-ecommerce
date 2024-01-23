"""project URL Configuration
"""

from django.urls import include, re_path

urlpatterns = [
    re_path(r"^api/v0/meta/", include("system_meta.urls")),
    re_path(r"^api/v0/payments/", include("payments.urls")),
]
