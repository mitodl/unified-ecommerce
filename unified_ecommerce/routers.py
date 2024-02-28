"""Base router classes for the app."""

from rest_framework.routers import SimpleRouter
from rest_framework_extensions.routers import NestedRouterMixin


class SimpleRouterWithNesting(NestedRouterMixin, SimpleRouter):
    """The DRF simpler router with the nested router mixin."""
