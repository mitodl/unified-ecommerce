"""API functions for authentication."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from oauthlib.oauth2 import (
    BackendApplicationClient,
    InvalidGrantError,
    TokenExpiredError,
)
from requests_oauthlib import OAuth2Session

from authentication.models import KeycloakAdminToken
from unified_ecommerce.celery import app

User = get_user_model()
log = logging.getLogger(__name__)


def keycloak_session_init(url, **kwargs):
    """
    Initialize a Keycloak session.

    This is a helper function that will initialize a Keycloak session with the
    provided URL. It will also handle refreshing the token if it has expired.

    Args:
    url (str): The Keycloak admin URL.
    **kwargs: Additional arguments to pass to the OAuth2Session initializer.

    Returns:
    None, or dict of data returned.
    """

    token_url = (
        f"{settings.KEYCLOAK_ADMIN_URL}/auth/realms/master/"
        "protocol/openid-connect/token"
    )
    client = BackendApplicationClient(client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID)

    auto_refresh_kwargs = {
        "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
    }

    def update_token(token):
        log_str = f"Refreshing Keycloak token {token}"
        log.warning(log_str)
        KeycloakAdminToken.objects.all().delete()
        KeycloakAdminToken.objects.create(
            authorization_token=token.get("access_token"),
            refresh_token=token.get("refresh_token", None),
            authorization_token_expires_in=token.get("access_token_expires_in", 60),
            refresh_token_expires_in=token.get("refresh_token_expires_in", 60),
        )

    def check_for_token():
        token = KeycloakAdminToken.latest()

        if not token:
            this_dumb_message_because_ruff_is_annoying = "No token found"
            raise TokenExpiredError(this_dumb_message_because_ruff_is_annoying)

        return token

    # Note: we call get_user_info here in both the try and the except because you won't
    # get a token error until you attempt to make a request.
    try:
        token = check_for_token()

        log_str = f"Trying to start up a session with token {token.token_formatted}"
        log.warning(log_str)

        session = OAuth2Session(
            client=client,
            token=token.token_formatted,
            auto_refresh_url=token_url,
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=update_token,
        )

        keycloak_info = session.get(url, **kwargs).json()
    except (InvalidGrantError, TokenExpiredError) as ige:
        log_str = f"Token error, trying to get a new token: {ige}"
        log.warning(log_str)

        session = OAuth2Session(client=client)
        token = session.fetch_token(
            token_url=token_url,
            client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID,
            client_secret=settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
            verify=False,
        )

        update_token(token)
        session = OAuth2Session(client=client, token=token)
        keycloak_info = session.get(url, **kwargs).json()

    log_str = f"Keycloak info returned: {keycloak_info}"
    log.warning(log_str)

    return keycloak_info


def keycloak_get_user(user: User):
    """Get a user from Keycloak."""

    userinfo_url = (
        f"{settings.KEYCLOAK_ADMIN_URL}/auth/admin/"
        f"realms/{settings.KEYCLOAK_ADMIN_REALM}/users/"
    )

    log_str = f"Trying to get user info for {user.username}"
    log.warning(log_str)

    if user.keycloak_user_tokens.exists():
        params = {"id": user.keycloak_user_tokens.first().keycloak_id}
    else:
        params = {"email": user.username}

    userinfo = keycloak_session_init(userinfo_url, verify=False, params=params)

    if len(userinfo) == 0:
        log.warning("Keycloak didn't return anything")
        return None

    return userinfo[0]


@app.task
def keycloak_update_user_account(user: int):
    """Update the user account using info from Keycloak asynchronously."""

    user = User.objects.get(id=user)

    keycloak_user = keycloak_get_user(user)

    if keycloak_user is None:
        return

    user.first_name = keycloak_user["firstName"]
    user.last_name = keycloak_user["lastName"]
    user.email = keycloak_user["email"]
    user.username = keycloak_user["id"]
    user.save()

    user.keycloak_user_tokens.all().delete()
    user.keycloak_user_tokens.create(keycloak_id=keycloak_user["id"])
    user.save()
