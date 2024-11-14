"""Django Admin screens for users."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as ContribUserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from users.models import UserProfile

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    """Admin view for the profile"""

    model = UserProfile
    classes = ["collapse"]

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """Return false."""

        return True


class UserAdmin(ContribUserAdmin):
    """Admin views for user"""

    include_created_on_in_list = True
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "password",
                    "last_login",
                )
            },
        ),
        (_("Personal Info"), {"fields": ("first_name", "last_name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ["collapse"],
            },
        ),
    )
    list_display = (
        "email",
        "username",
        "is_staff",
        "last_login",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email")
    ordering = ("email",)
    readonly_fields = ("last_login", "password")
    inlines = [UserProfileInline]


admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
