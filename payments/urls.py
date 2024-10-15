"""URLs for the payments app."""

from django.urls import include, re_path

from payments.views.v0.urls import urlpatterns as v0_urls

urlpatterns = [
    re_path(r"^api/v0/payments/", include((v0_urls, "v0"))),
]
