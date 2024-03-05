"""Middleware for Unified Ecommerce."""

import base64
import json
import logging

from django.contrib.auth.middleware import RemoteUserMiddleware

log = logging.getLogger(__name__)


class ApisixUserMiddleware:
    """Checks for and processes APISIX-specific headers."""

    def decode_apisix_headers(self, request):
        """Decode the APISIX-specific headers."""
        user_info = request.META.get("HTTP_X_USERINFO", False)

        if not user_info:
            return None

        try:
            apisix_result = json.loads(base64.b64decode(user_info))
        except json.JSONDecodeError:
            log_message = (
                "ApisixUserMiddleware: Result from HTTP_X_USERINFO "
                f"is not valid JSON: {user_info}"
            )
            log.debug(log_message)

            return None

        log_message = f"ApisixUserMiddleware: Got {apisix_result}"
        log.debug(log_message)

        return {
            "email": apisix_result["email"],
            "preferred_username": apisix_result["preferred_username"],
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
