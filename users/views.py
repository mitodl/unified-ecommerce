"""Views for the users app."""

from django.conf import settings
from django.shortcuts import redirect
from django.views.generic import TemplateView
from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from system_meta.models import IntegratedSystem
from unified_ecommerce.serializers import UserSerializer


class LoggedOutView(TemplateView):
    """View for the logged out page."""

    template_name = "logged_out.html"


class CurrentUserRetrieveViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """User retrieve and update viewsets for the current user"""

    serializer_class = UserSerializer
    permission_classes = (AllowAny,)

    def get_object(self):
        """Return the current request user"""
        # NOTE: this may be a logged in or anonymous user
        return self.request.user


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def establish_session(request):
    """
    Establish a session, then redirect to the basket page.

    Set `next` to the integrated system you're working in, and the user will be
    sent to the cart for that system afterwards. Otherwise, this will go to the
    session check API endpoint.
    """

    if "next" in request.GET:
        try:
            system = IntegratedSystem.objects.get(slug=request.GET["next"])
            next_url = f"{settings.MITOL_UE_PAYMENT_BASKET_ROOT}{system.slug}/"
        except IntegratedSystem.DoesNotExist:
            next_url = settings.MITOL_UE_PAYMENT_BASKET_CHOOSER

    next_url = request.session.get("next", next_url)

    return redirect(next_url)
