"""App initialization for authentication"""

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    """Config for the authentication app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "authentication"
