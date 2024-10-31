"""App initialization for users"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Config for the users app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
