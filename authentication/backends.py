"""User backends for authentication."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import RemoteUserBackend

from authentication.api import keycloak_session_init

log = logging.getLogger(__name__)

User = get_user_model()


class KeycloakRemoteUserBackend(RemoteUserBackend):
    """
    Backend for user auth that uses Keycloak to resolve the user's email address.

    The RemoteUserBackend mostly covers what we want; however, the
    X-Forwarded-User is always an email address, and users can change those. So, we
    need to first hit the Keycloak API to figure out what their UUID is and create the
    user with that instead.
    """

    def authenticate(self, request, remote_user):
        """Authenticate the user, using Keycloak to grab their ID first."""

        log.debug("KeycloakRemoteUserBackend is running for %s", remote_user)

        userinfo_url = (
            f"{settings.KEYCLOAK_ADMIN_URL}"
            f"/admin/realms/{settings.KEYCLOAK_REALM}/users/"
        )

        if not remote_user:
            log.debug("No remote_user provided")
            return None

        userinfo = keycloak_session_init(
            userinfo_url, verify=False, params={"email": remote_user}
        )

        if len(userinfo) == 0:
            log.debug("Keycloak didn't return anything")
            # User may have changed their email, so let's see if we can find an
            # existing user

            existing_user = User.objects.get(email=remote_user)

            if existing_user is not None:
                log.debug(
                    "Found existing user %s, trying to get Keycloak info for them",
                    existing_user,
                )
                userinfo = [
                    keycloak_session_init(
                        f"{userinfo_url}{existing_user.username}/", verify=False
                    )
                ]

                if len(userinfo) == 0:
                    log.debug(
                        "Keycloak still returned nothing for ID %s, so giving up.",
                        existing_user.username,
                    )
                    return None
            else:
                log.debug(
                    "Keycloak still returned nothing and we didn't find a user to"
                    " check, so giving up."
                )
                return None

        authenticated_user = super().authenticate(request, userinfo[0]["id"])

        if authenticated_user is not None:
            # We might as well go ahead and update the record here too.
            authenticated_user.email = userinfo[0]["email"]
            authenticated_user.first_name = userinfo[0]["firstName"]
            authenticated_user.last_name = userinfo[0]["lastName"]
            authenticated_user.save()

        return authenticated_user
