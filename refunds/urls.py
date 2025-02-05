"""URL routing for the refunds app."""

from django.urls import include, path

from refunds.views.v0 import create_from_order

urlpatterns = [
    path("", include("refunds.views.v0.urls")),
    path("create_from_order", create_from_order),
]
