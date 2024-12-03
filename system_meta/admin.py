"""Django Admin for system_meta app"""

from django.contrib import admin
from rest_framework_api_key.admin import APIKeyModelAdmin
from reversion.admin import VersionAdmin
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter, highlight_deleted

from system_meta.models import IntegratedSystem, IntegratedSystemAPIKey, Product


class IntegratedSystemAdmin(SafeDeleteAdmin):
    """Admin for IntegratedSystem model"""

    list_display = (
        highlight_deleted,
        "highlight_deleted_field",
        "name",
        "description",
        *SafeDeleteAdmin.list_display,
    )
    list_filter = ("name", SafeDeleteAdminFilter, *SafeDeleteAdmin.list_filter)
    field_to_highlight = "id"


IntegratedSystemAdmin.highlight_deleted_field.short_description = (
    IntegratedSystemAdmin.field_to_highlight
)


@admin.register(IntegratedSystemAPIKey)
class IntegratedSystemAPIKeyAdmin(APIKeyModelAdmin):
    pass


class ProductAdmin(SafeDeleteAdmin, VersionAdmin):
    """Admin for Product model"""

    list_display = (
        highlight_deleted,
        "highlight_deleted_field",
        "sku",
        "name",
        "price",
        "system",
        *SafeDeleteAdmin.list_display,
    )
    list_filter = (
        "sku",
        "name",
        "system",
        SafeDeleteAdminFilter,
        *SafeDeleteAdmin.list_filter,
    )
    field_to_highlight = "id"


ProductAdmin.highlight_deleted_field.short_description = ProductAdmin.field_to_highlight


admin.site.register(IntegratedSystem, IntegratedSystemAdmin)
admin.site.register(Product, ProductAdmin)
