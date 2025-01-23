"""Views for the users app."""

from urllib.parse import urljoin

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

    This has two modes.

    * Set `next` to the integrated system you're working in, and the user will be
    sent to the cart for that system afterwards. Otherwise, this will go to the
    session check API endpoint.

    * Set `system` to the integrated system you're in, and `next` to the next
    URL (within the system's URL-space) to send the user back to. This will set
    up the user, then send them back into the integrated system.
    """

    next_url = settings.MITOL_UE_PAYMENT_BASKET_CHOOSER

    if "next" in request.GET:
        if "system" in request.GET:
            try:
                system = IntegratedSystem.objects.get(slug=request.GET["system"])
                next_url = request.GET["next"]
                next_url = urljoin(system.homepage_url, next_url)
            except IntegratedSystem.DoesNotExist:
                return redirect(settings.MITOL_UE_PAYMENT_BASKET_CHOOSER)
        else:
            try:
                system = IntegratedSystem.objects.get(slug=request.GET["next"])
                next_url = urljoin(
                    settings.MITOL_UE_PAYMENT_BASKET_ROOT, f"?system={system.slug}"
                )
            except IntegratedSystem.DoesNotExist:
                return redirect(settings.MITOL_UE_PAYMENT_BASKET_CHOOSER)

    return redirect(next_url)
