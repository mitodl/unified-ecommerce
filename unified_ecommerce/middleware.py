"""Middleware for Unified Ecommerce."""

import json
import logging

from django.contrib.auth.middleware import RemoteUserMiddleware

from unified_ecommerce.utils import decode_x_header

log = logging.getLogger(__name__)


class ApisixUserMiddleware:
    """Checks for and processes APISIX-specific headers."""

    def decode_apisix_headers(self, request):
        """Decode the APISIX-specific headers."""

        try:
            apisix_result = decode_x_header(request, "HTTP_X_USERINFO")
            if not apisix_result:
                log.debug(
                    "No APISIX-specific header found",
                )
                return None
        except json.JSONDecodeError:
            log.debug(
                "Got bad APISIX-specific header: %s",
                request.META.get("HTTP_X_USERINFO", ""),
            )

            return None

        log.debug("ApisixUserMiddleware: Got %s", apisix_result)

        return {
            "email": apisix_result["email"],
            "preferred_username": apisix_result["sub"],
            "given_name": apisix_result["given_name"],
            "family_name": apisix_result["family_name"],
        }

    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response

    def __call__(self, request):
        """
        Process any APISIX headers and put them in the request.

        If valid data is found, then it will be put into the "api_gateway_userdata"
        attribute of the request. Otherwise, it'll be set to None.
        """

        request.api_gateway_userdata = self.decode_apisix_headers(request)

        return self.get_response(request)


class ForwardUserMiddleware(RemoteUserMiddleware):
    """RemoteUserMiddleware, but looks at X-Forwarded-User"""

    header = "HTTP_X_FORWARDED_USER"
