"""Authentication related models."""
# ruff: noqa: TD002,TD003,FIX002

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models
from mitol.common.models import TimestampedModel
from mitol.common.utils import now_in_utc

User = get_user_model()


class KeycloakUserToken(TimestampedModel):
    """Stores the Keycloak ID for users."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="keycloak_user_tokens"
    )
    keycloak_id = models.CharField(
        max_length=255, unique=True, default=None, null=True, blank=True
    )

    def __str__(self):
        """Return string version of the KeycloakUserToken."""
        return f"{self.user} {{{self.keycloak_id}}}"


class KeycloakAdminToken(TimestampedModel):
    """Stores OAuth tokens for the Keycloak admin API"""

    authorization_token = models.TextField()
    refresh_token = models.TextField(blank=True, default="")
    authorization_token_expires_in = models.IntegerField(
        help_text="Seconds until authentication token expires"
    )
    refresh_token_expires_in = models.IntegerField(
        null=True, help_text="Seconds until refresh token expires"
    )

    def calculate_token_expiration(self) -> (int, int):
        """Calculate the expiration time of the tokens."""

        access_expires_on = self.created_on + timedelta(
            seconds=self.authorization_token_expires_in
        )
        refresh_expires_on = (
            self.created_on + timedelta(seconds=self.refresh_token_expires_in)
            if self.refresh_token
            else None
        )

        access_seconds_left = (access_expires_on - now_in_utc()).total_seconds()
        refresh_seconds_left = (
            (refresh_expires_on - now_in_utc()).total_seconds()
            if refresh_expires_on
            else -1
        )

        return (access_seconds_left, refresh_seconds_left)

    @property
    def token_formatted(self):
        """Return the token info in a format that request-oauthlib can use."""

        seconds_left = self.calculate_token_expiration()

        return {
            "access_token": self.authorization_token,
            "token_type": "Bearer",
            "expires_in": seconds_left[0],
            "refresh_token": self.refresh_token,
            "refresh_token_expires_in": seconds_left[1],
        }

    @staticmethod
    def latest():
        """Return the latest token."""

        try:
            return KeycloakAdminToken.objects.latest("created_on")
        except KeycloakAdminToken.DoesNotExist:
            # New token is handled by the util function to get keycloak data
            return None

    def __str__(self):
        """Return a string representation of the token."""

        expires_at = self.created_on + timedelta(
            seconds=self.authorization_token_expires_in
        )
        refresh_expires_at = (
            self.created_on + timedelta(seconds=self.refresh_token_expires_in)
            if self.refresh_token
            else None
        )
        expired = "EXPIRED " if now_in_utc() > expires_at else ""

        return (
            f"{expired}Auth token created {self.created_on} expires {expires_at} "
            f"refresh expires {refresh_expires_at}"
        )
