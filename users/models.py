"""Models for users and profiles."""
# ruff: noqa: TD002,TD003,FIX002

import logging

from django.contrib.auth import get_user_model
from django.db import models
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel

User = get_user_model()
log = logging.getLogger(__name__)


class UserProfile(TimestampedModel):
    """Provides additional fields for userdata."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    country_code = CountryField()
