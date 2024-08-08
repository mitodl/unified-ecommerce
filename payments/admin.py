"""Django Admin for system_meta app"""

from django.contrib import admin
from django.contrib.admin.decorators import display
from fsm_admin.mixins import FSMTransitionMixin
from mitol.common.admin import TimestampedModelAdmin
from reversion.admin import VersionAdmin

from payments import models


@admin.register(models.Basket)
class BasketAdmin(VersionAdmin):
    """Admin for Basket"""

    model = models.Basket
    search_fields = ["user__email", "user__username"]
    list_display = ["id", "user"]
    raw_id_fields = ("user",)


@admin.register(models.BasketItem)
class BasketItemAdmin(VersionAdmin):
    """Admin for BasketItem"""

    model = models.BasketItem
    search_fields = ["product__description", "product__price"]
    list_display = ["id", "product", "quantity"]
    raw_id_fields = ("basket", "product")


class OrderLineInline(admin.TabularInline):
    """Inline editor for lines"""

    model = models.Line
    readonly_fields = ["unit_price", "total_price", "discounted_price"]
    min_num = 1
    extra = 0


class OrderTransactionInline(admin.TabularInline):
    """Inline editor for transactions for an Order"""

    def has_add_permission(self, request, obj=None):  # noqa: ARG002
        """Disable adding transactions"""
        return False

    model = models.Transaction
    readonly_fields = ["order", "amount", "data"]
    min_num = 0
    extra = 0
    can_delete = False
    can_add = False


class BaseOrderAdmin(FSMTransitionMixin, TimestampedModelAdmin):
    """Base admin for Order"""

    search_fields = [
        "id",
        "purchaser__email",
        "purchaser__username",
        "reference_number",
    ]
    list_display = ["id", "state", "get_purchaser", "total_price_paid"]
    list_fields = ["state"]
    list_filter = ["state"]
    inlines = [OrderLineInline, OrderTransactionInline]
    readonly_fields = ["reference_number"]

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Disable adding orders"""
        return False

    @display(description="Purchaser")
    def get_purchaser(self, obj: models.Order):
        """Return the purchaser information for the order"""
        return f"{obj.purchaser.name} ({obj.purchaser.email})"

    def get_queryset(self, request):
        """Filter only to pending orders"""
        return (
            super()
            .get_queryset(request)
            .prefetch_related("purchaser", "lines__product_version")
        )


@admin.register(models.Order)
class OrderAdmin(BaseOrderAdmin):
    """Admin for Order"""

    list_display = ["id", "state", "purchaser", "total_price_paid", "reference_number"]
    model = models.Order


@admin.register(models.PendingOrder)
class PendingOrderAdmin(BaseOrderAdmin):
    """Admin for PendingOrder"""

    model = models.PendingOrder

    def get_queryset(self, request):
        """Filter only to pending orders"""
        return super().get_queryset(request).filter(state=models.Order.STATE.PENDING)


@admin.register(models.CanceledOrder)
class CanceledOrderAdmin(BaseOrderAdmin):
    """Admin for CanceledOrder"""

    model = models.CanceledOrder

    def get_queryset(self, request):
        """Filter only to canceled orders"""
        return super().get_queryset(request).filter(state=models.Order.STATE.CANCELED)


@admin.register(models.FulfilledOrder)
class FulfilledOrderAdmin(BaseOrderAdmin):
    """Admin for FulfilledOrder"""

    model = models.FulfilledOrder

    def get_queryset(self, request):
        """Filter only to fulfilled orders"""
        return (
            super()
            .get_queryset(request)
            .prefetch_related("purchaser", "lines__product_version")
            .filter(state=models.Order.STATE.FULFILLED)
        )


@admin.register(models.RefundedOrder)
class RefundedOrderAdmin(BaseOrderAdmin):
    """Admin for RefundedOrder"""

    model = models.RefundedOrder

    def get_queryset(self, request):
        """Filter only to refunded orders"""
        return super().get_queryset(request).filter(state=models.Order.STATE.REFUNDED)
