"""Common viewsets for Unified Ecommerce."""

import logging

from rest_framework import viewsets

log = logging.getLogger(__name__)


class AuthVariegatedModelViewSet(viewsets.ModelViewSet):
    """
    Viewset with customizable serializer based on user authentication.

    This bifurcates the ModelViewSet so that if the user is a read-only user (i.e.
    not a staff or superuser, or not logged in), they get a separate "read-only"
    serializer. Otherwise, we use a regular serializer. The read-only serializer can
    then have different fields so you can hide irrelevant data from anonymous users.

    You will need to enforce the read-onlyness of the API yourself; use something like
    the IsAuthenticatedOrReadOnly permission class or do something in the serializer.

    Set read_write_serializer_class to the serializer you want to use for admins and
    set read_only_serializer_class to the one for regular users.
    """

    read_write_serializer_class = None
    read_only_serializer_class = None

    def get_serializer_class(self):
        """Get the serializer class for the route."""

        if hasattr(self, "request") and (
            self.request.user.is_staff or self.request.user.is_superuser
        ):
            log.debug("get_serializer_class returning the Admin one")
            return self.read_write_serializer_class

        log.debug("get_serializer_class returning the regular one")
        return self.read_only_serializer_class
