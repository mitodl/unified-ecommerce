"""Middleware for Unified Ecommerce."""

import logging

from django.contrib.auth import login, logout
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.exceptions import ImproperlyConfigured

from unified_ecommerce.utils import decode_apisix_headers, get_user_from_apisix_headers

log = logging.getLogger(__name__)


class ApisixUserMiddleware(RemoteUserMiddleware):
    """Checks for and processes APISIX-specific headers."""

    def process_request(self, request):
        """
        Check the request for an authenticated user, or authenticate using the
        APISIX data if there isn't one.
        """

        if not hasattr(request, "user"):
            msg = "ApisixUserMiddleware requires the authentication middleware."
            raise ImproperlyConfigured(msg)

        try:
            apisix_user = get_user_from_apisix_headers(request)
        except KeyError:
            if self.force_logout_if_no_header and request.user.is_authenticated:
                logout(request)
            return None

        if apisix_user:
            if request.user.is_authenticated and request.user != apisix_user:
                # The user is authenticated, but doesn't match the user we got
                # from APISIX. So, log them out so the APISIX user takes
                # precedence.

                logout(request)

            request.user = apisix_user
            login(
                request,
                apisix_user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

        request.api_gateway_userdata = decode_apisix_headers(request)

        return self.get_response(request)
