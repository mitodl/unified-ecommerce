"""Models for users and profiles."""
# ruff: noqa: TD002,TD003,FIX002

import logging
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models, transaction
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel

log = logging.getLogger(__name__)


def _post_create_user(user):
    """
    Create records related to the user.

    Args:
        user (users.models.User): the user that was just created
    """
    UserProfile.objects.create(user=user)


class UserManager(BaseUserManager):
    """User manager for custom user model"""

    use_in_migrations = True

    @transaction.atomic
    def _create_user(self, username, email, password, **extra_fields):
        """Create and save a user with the given email and password"""
        email = self.normalize_email(email)
        fields = {**extra_fields, "email": email}
        if username is not None:
            fields["username"] = username
        user = self.model(**fields)
        user.set_password(password)
        user.save(using=self._db)
        _post_create_user(user)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        """Create a user"""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        """Create a superuser"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            msg = "Superuser must have is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Superuser must have is_superuser=True."
            raise ValueError(msg)

        return self._create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, TimestampedModel, PermissionsMixin):
    """Primary user class"""

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "global_id"
    REQUIRED_FIELDS = ["email", "name"]

    # global_id points to the SSO ID for the user (so, usually the Keycloak ID,
    # which is a UUID). We store it as a string in case the SSO source changes.
    # We allow a blank value so we can have out-of-band users - we may want a
    # Django user that's not connected to an SSO user, for instance.
    global_id = models.CharField(
        unique=True,
        max_length=255,
        blank=True,
        default=uuid4,
        help_text="The SSO ID (usually a Keycloak UUID) for the user.",
    )
    username = models.CharField(unique=True, max_length=150)
    email = models.EmailField(blank=False, unique=True)
    first_name = models.CharField(blank=True, default="", max_length=255)
    last_name = models.CharField(blank=True, default="", max_length=255)
    name = models.CharField(blank=True, default="", max_length=255)
    is_staff = models.BooleanField(
        default=False, help_text="The user can access the admin site"
    )
    is_active = models.BooleanField(
        default=True, help_text="The user account is active"
    )

    objects = UserManager()

    @property
    def is_global(self) -> bool:
        """Return True if the user is a global user (was created via SSO)"""
        return self.global_id != ""

    def __str__(self):
        """Str representation for the user"""
        return (
            f"User global_id={self.global_id} username={self.username} "
            f"email={self.email}"
        )


class UserProfile(TimestampedModel):
    """Provides additional fields for userdata."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    country_code = CountryField()
