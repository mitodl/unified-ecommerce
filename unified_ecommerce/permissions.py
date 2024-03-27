"""Custom DRF permissions."""

from rest_framework import permissions


class IsAdminUserOrReadOnly(permissions.BasePermission):
    """Determines if the user owns the object"""

    def has_permission(self, request, view):  # noqa: ARG002
        """
        Return True if the user is an admin user requesting a write operation,
        or if the user is logged in. Otherwise, return False.
        """

        if request.method in permissions.SAFE_METHODS or (
            request.user.is_authenticated and request.user.is_staff
        ):
            return True

        return False
