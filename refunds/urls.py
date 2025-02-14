"""URL routing for the refunds app."""

from django.urls import include, re_path

from refunds.views.v0.urls import urlpatterns as v0_urls

urlpatterns = [
    re_path("^api/v0/refunds/", include((v0_urls, "v0"))),
]
