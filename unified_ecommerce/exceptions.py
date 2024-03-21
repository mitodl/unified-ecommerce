"""Exceptions for Unified Ecommerce"""

from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """
    Handles API exceptions by appending extra info
    """  # noqa: D401
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # now add the error type to the response
    # sometimes this is a list() if such an api was called
    if response is not None and isinstance(response.data, dict):
        response.data["error_type"] = exc.__class__.__name__

    return response


class DoNotUseRequestException(Exception):  # noqa: N818
    """This exception is raised during unit tests if an HTTP request is attempted"""

class KeycloakAuthError(Exception):
    """Raised if Keycloak returns an error when attempting to pull user data."""
