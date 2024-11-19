"""Routes for the users app."""

from django.urls import include, re_path

from users.views import (
    CurrentUserRetrieveViewSet,
    LoggedOutView,
    establish_session,
)

v0_urls = [
    re_path(
        r"^me/$",
        CurrentUserRetrieveViewSet.as_view({"get": "retrieve"}),
    ),
]

urlpatterns = [
    re_path(
        r"^logged_out/$",
        LoggedOutView.as_view(),
        name="logged_out_page",
    ),
    re_path(
        r"^establish_session/$",
        establish_session,
        name="users-establish_session",
    ),
    re_path(r"^api/v0/users/", include((v0_urls, "v0"))),
]
