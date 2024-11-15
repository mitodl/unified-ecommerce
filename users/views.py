"""Views for the users app."""

from django.views.generic import TemplateView
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

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
