"""Custom authentication for DRF"""

import logging
import random
import string

import jwt
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

User = get_user_model()

HEADER_PREFIX = "Token "
HEADER_PREFIX_LENGTH = len(HEADER_PREFIX)

log = logging.getLogger()


class IgnoreExpiredJwtAuthentication(JSONWebTokenAuthentication):
    """Version of JSONWebTokenAuthentication that ignores JWT values if they're expired"""  # noqa: E501

    @classmethod
    def get_token_from_request(cls, request):
        """Returns the JWT values as long as it's not expired"""  # noqa: D401
        value = super().get_token_from_request(request)

        try:
            # try to decode the value just to see if it's expired
            from rest_framework_jwt.settings import api_settings

            jwt_decode_handler = api_settings.JWT_DECODE_HANDLER
            jwt_decode_handler(value)
        except jwt.ExpiredSignatureError:
            # if it is expired, treat it as if the user never passed a token
            log.debug("Ignoring expired JWT")
            return None
        except:  # pylint: disable=bare-except  # noqa: E722, S110
            # we're only interested in jwt.ExpiredSignature above
            # exception handling in general is already handled in the base class
            pass

        return value


class StatelessTokenAuthentication(BaseAuthentication):
    """
    Stateless authentication via a authorization token

    NOTE: this is a highly trusting version of authentication and should only be
          used for certain things such as email unsubscribes
    """

    def authenticate(self, request):
        """
        Attempts to authenticate using a stateless token
        """  # noqa: D401
        from unified_ecommerce.auth_utils import unsign_and_verify_username_from_token

        if "HTTP_AUTHORIZATION" in request.META:
            header_value = request.META["HTTP_AUTHORIZATION"]

            if not header_value.startswith(HEADER_PREFIX):
                return None

            token = header_value[HEADER_PREFIX_LENGTH:]

            username = unsign_and_verify_username_from_token(token)

            if not username:
                return None

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None

            return (user, None)

        return None


class ApiGatewayAuthentication(BaseAuthentication):
    """
    Handles authentication when behind an API gateway.

    If the app is sitting in front of something like APISIX, the app will get
    authentication information through some sort of channel. A middleware can
    take care of decoding that and placing the decoded data into the request,
    and this backend will handle the authentication based on that data.
    """

    def authenticate(self, request):
        """Authenticate the user based on request.api_gateway_userdata."""

        if (
            not request
            or not request.api_gateway_userdata
        ):
            return None

        (
            email,
            preferred_username,
            given_name,
            family_name,
        ) = request.api_gateway_userdata

        try:
            user = User.objects.filter(email=email).get()

            log.debug(
                "ApiGatewayAuthentication: Found existing user for %s: %s",
                preferred_username,
                user,
            )
        except User.DoesNotExist:
            log.debug(
                "ApiGatewayAuthentication: User %s not found, creating",
                preferred_username,
            )
            # Create a random password for the user, 32 characters long.
            # We don't care about the password since APISIX (or whatever) has
            # bounced the user to an authentication system elsewhere (like Keycloak).
            user = User.objects.create_user(
                preferred_username,
                email,
                "".join(random.choices(string.ascii_uppercase + string.digits, k=32)),  # noqa: S311
            )

            user.first_name = given_name
            user.last_name = family_name
            user.save()

        return (user, None)
