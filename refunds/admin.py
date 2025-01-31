"""Admin for the refunds app."""

from django.contrib import admin

from refunds.models import Request, RequestRecipient


class RequestRecipientAdmin(admin.ModelAdmin):
    """Admin for RequestRecipient."""

    list_display = ("email", "system")
    search_fields = ("email", "system")
    list_filter = ("system",)


class RequestAdmin(admin.ModelAdmin):
    """Admin for Request."""

    list_display = ("requester_email", "order", "processed_date", "processed_by_email")

    @admin.display(description="Requester")
    def requester_email(self, obj):
        """Return the requester's email."""
        return obj.requester.email

    @admin.display(description="Processed by")
    def processed_by_email(self, obj):
        """Return the processed by user's email."""
        return obj.processed_by.email


admin.site.register(RequestRecipient, RequestRecipientAdmin)
admin.site.register(Request, RequestAdmin)
