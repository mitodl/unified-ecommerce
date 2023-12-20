"""App initialization for payments"""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Config for the payments app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"
