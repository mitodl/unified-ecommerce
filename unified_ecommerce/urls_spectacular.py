"""project URL Configuration"""

from django.urls import include, re_path

urlpatterns = [
    re_path(r"", include("system_meta.urls")),
]
