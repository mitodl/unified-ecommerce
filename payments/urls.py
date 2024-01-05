"""URLs for the payments app."""

from django.urls import include, re_path

from payments.views.v0.urls import router as v0_router

urlpatterns = [
    re_path(r"^v0/", include(v0_router.urls)),
]
