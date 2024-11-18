"""Views for the users app."""

from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from unified_ecommerce.serializers import UserSerializer


class LoggedOutView(TemplateView):
    """View for the logged out page."""

    template_name = "logged_out.html"


class CurrentUserRetrieveViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """User retrieve and update viewsets for the current user"""

    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        """Return the current request user"""
        # NOTE: this may be a logged in or anonymous user
        return self.request.user


@api_view(["GET"])
@permission_classes([AllowAny])
def session_check(request):
    """
    Check for an active user session.

    If a session doesn't exist, then redirect the user to a route that requires
    the APISIX middleware, so they can then have a session.
    """

    if request.user.is_authenticated:
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    next_url = (
        request.GET["next"] if "next" in request.GET else reverse("users-session_check")
    )

    request.session["next"] = next_url

    return Response(
        {
            "detail": "User is not authenticated",
            "next": request.session.get("next", "/"),
        },
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def establish_session(request):
    """Establish a session, then redirect to a "next" setting if there is one."""

    next_url = (
        request.GET["next"] if "next" in request.GET else reverse("users-session_check")
    )
    next_url = request.session.get("next", next_url)

    return redirect(next_url)
