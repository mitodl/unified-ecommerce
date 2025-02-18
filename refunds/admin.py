"""Admin for the refunds app."""

from django.contrib import admin

from refunds.models import Request, RequestLine, RequestProcessingCode, RequestRecipient


class ProcessingCodeInline(admin.TabularInline):
    """Inline for processing codes."""

    model = RequestProcessingCode
    fields = [
        "code_batch",
        "email",
        "approve_code",
        "deny_code",
        "code_active",
        "code_used",
        "code_used_on",
    ]
    readonly_fields = [
        "code_batch",
        "email",
        "approve_code",
        "deny_code",
        "code_active",
        "code_used",
        "code_used_on",
    ]
    min_num = 0
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj):  # noqa: ARG002
        """Disable add permission."""

        return False


class RequestLineInline(admin.TabularInline):
    """Inline for lines"""

    model = RequestLine
    fields = [
        "status",
        "line",
        "line_amount",
        "refunded_amount",
    ]
    readonly_fields = [
        "status",
        "line",
        "line_amount",
        "refunded_amount",
    ]
    min_num = 0
    extra = 0
    can_delete = False

    @admin.display(description="Charge Amount")
    def line_amount(self, obj):
        """Return the amount of the line."""

        return obj.line.total_price

    def has_add_permission(self, request, obj):  # noqa: ARG002
        """Disable add permission."""

        return False


class RequestRecipientAdmin(admin.ModelAdmin):
    """Admin for RequestRecipient."""

    list_display = ("email", "integrated_system")
    search_fields = ("email", "integrated_system")
    list_filter = ("integrated_system",)


class RequestAdmin(admin.ModelAdmin):
    """Admin for Request."""

    list_display = (
        "id",
        "status",
        "requester_email",
        "system",
        "order",
        "line_count",
        "total_requested",
        "total_approved",
        "processed_date",
        "processed_by_email",
    )
    list_filte = ("status",)
    inlines = [
        RequestLineInline,
        ProcessingCodeInline,
    ]
    fields = [
        "requester",
        "order",
        "status",
        "total_requested",
        "total_approved",
        "processed_date",
        "processed_by",
        "zendesk_ticket",
    ]
    readonly_fields = [
        "requester",
        "order",
        "total_requested",
        "total_approved",
    ]

    @admin.display(description="System")
    def system(self, obj):
        """Return the system for this request."""

        return obj.order.integrated_system

    @admin.display(description="Line Count")
    def line_count(self, obj):
        """Return the number of lines on the request."""
        return obj.lines.count()

    @admin.display(description="Requester")
    def requester_email(self, obj):
        """Return the requester's email."""
        return obj.requester.email

    @admin.display(description="Processed by")
    def processed_by_email(self, obj):
        """Return the processed by user's email."""
        return obj.processed_by.email if obj.processed_by else None


class RequestProcessingCodeAdmin(admin.ModelAdmin):
    """Admin for processing codes."""

    list_display = ("refund_request", "code_batch", "email", "code_active", "code_used")
    search_fields = ("email", "code_batch")
    list_filter = ("code_active", "code_used")


admin.site.register(RequestRecipient, RequestRecipientAdmin)
admin.site.register(Request, RequestAdmin)
admin.site.register(RequestProcessingCode, RequestProcessingCodeAdmin)
