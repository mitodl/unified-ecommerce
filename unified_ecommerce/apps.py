"""
Root app config for the project.
"""

from django.apps import AppConfig


class RootConfig(AppConfig):
    """AppConfig for this project"""

    name = "unified_ecommerce"

    def ready(self):
        """Set up PostHog."""

        from mitol.common import envs
        from mitol.olposthog.features import configure

        envs.validate()
        configure()
