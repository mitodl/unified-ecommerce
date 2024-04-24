"""Middleware for Unified Ecommerce."""

import logging

from django.contrib.auth import login
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.exceptions import ImproperlyConfigured

from authentication.api import get_user_from_apisix_headers

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
                self._remove_invalid_user(request)
            return

        if request.user.is_authenticated:
            # The user is authenticated but like the RemoteUserMiddleware we
            # should now check and make sure the user APISIX is passing is
            # the same user.

            if request.user != apisix_user:
                self._remove_invalid_user(request)

            return

        if not apisix_user:
            self._remove_invalid_user(request)

            return

        request.user = apisix_user
        login(request, apisix_user, backend="django.contrib.auth.backends.ModelBackend")

        return


class ForwardUserMiddleware(RemoteUserMiddleware):
    """RemoteUserMiddleware, but looks at X-Forwarded-User"""

    header = "HTTP_X_FORWARDED_USER"
