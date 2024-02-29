"""App initialization for cart"""

from django.apps import AppConfig


class CartConfig(AppConfig):
    """Config for the cart app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cart"
