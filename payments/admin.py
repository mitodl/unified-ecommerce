"""Django Admin for system_meta app"""

from django.contrib import admin
from django.contrib.admin.decorators import display
from mitol.common.admin import TimestampedModelAdmin
from reversion.admin import VersionAdmin
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter

from payments import models


class BasketItemInline(admin.TabularInline):
    """Inline editor for lines"""

    model = models.BasketItem
    list_display = [
        "product",
        "quantity",
        "base_price",
        "discounted_price",
        "tax_money",
        "total_price",
    ]
    readonly_fields = [
        "product",
        "quantity",
        "base_price",
        "discounted_price",
        "tax_money",
        "total_price",
    ]
    min_num = 0
    extra = 0


@admin.register(models.Basket)
class BasketAdmin(VersionAdmin):
    """Admin for Basket"""

    model = models.Basket
    search_fields = ["user__email", "user__username"]
    list_display = ["id", "user"]
    raw_id_fields = ("user",)
    inlines = [
        BasketItemInline,
    ]


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
    readonly_fields = [
        "unit_price",
        "discounted_price",
        "tax_money",
        "total_price",
    ]
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


class BaseOrderAdmin(TimestampedModelAdmin):
    """Base admin for Order"""

    search_fields = [
        "id",
        "purchaser__email",
        "purchaser__username",
        "reference_number",
    ]
    list_display = ["id", "state", "get_purchaser", "total_price_paid", "tax"]
    list_fields = ["state"]
    list_filter = ["state"]
    inlines = [OrderLineInline, OrderTransactionInline]
    readonly_fields = ["reference_number"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "state",
                    "reference_number",
                    "integrated_system",
                    "created_on",
                    "updated_on",
                ]
            },
        ),
        (
            "Purchaser",
            {
                "fields": [
                    "purchaser",
                    "purchaser_ip",
                    "purchaser_taxable_country_code",
                    "purchaser_taxable_geolocation_type",
                    "purchaser_blockable_country_code",
                    "purchaser_blockable_geolocation_type",
                ],
            },
        ),
        (
            "Value",
            {
                "fields": [
                    "subtotal",
                    "discounts_applied",
                    "tax",
                    "total_price_paid",
                ]
            },
        ),
    ]

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Disable adding orders"""
        return False

    @display(description="Purchaser")
    def get_purchaser(self, obj: models.Order):
        """Return the purchaser information for the order"""
        return f"{obj.purchaser.email}"

    @display(description="Tax")
    def get_tax(self, obj: models.Order):
        """Return the tax for the order"""
        return obj.tax

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


@admin.register(models.Discount)
class DiscountAdmin(VersionAdmin):
    model = models.Discount
    search_fields = ["discount_type", "redemption_type", "discount_code"]
    list_display = [
        "id",
        "discount_code",
        "discount_type",
        "amount",
        "redemption_type",
        "payment_type",
    ]
    list_filter = ["discount_type", "redemption_type", "payment_type"]


@admin.register(models.RedeemedDiscount)
class RedeemedDiscountAdmin(admin.ModelAdmin):
    """Admin for RedeemedDiscount"""

    model = models.RedeemedDiscount
    search_fields = ["discount", "order", "user"]
    list_display = [
        "id",
        "discount",
        "order",
        "user",
    ]
    list_filter = ["discount", "order", "user"]


@admin.register(models.BulkDiscountCollection)
class BulkDiscountCollectionAdmin(VersionAdmin):
    """Admin for BulkDiscountCollection"""

    model = models.BulkDiscountCollection
    search_fields = ["prefix"]
    list_display = [
        "prefix",
    ]
    list_filter = ["prefix"]


@admin.register(models.BlockedCountry)
class BlockedCountryAdmin(SafeDeleteAdmin):
    """Admin for BlockedCountry"""

    model = models.BlockedCountry
    list_display = ["country_code", "product"]
    list_filter = [
        SafeDeleteAdminFilter,
        "product",
        "country_code",
    ]


@admin.register(models.TaxRate)
class TaxRateAdmin(SafeDeleteAdmin):
    """Admin for TaxRate"""

    model = models.TaxRate
    list_display = ["tax_rate", "tax_rate_name", "country_code"]
    list_filter = [
        SafeDeleteAdminFilter,
        "tax_rate_name",
        "country_code",
    ]


@admin.register(models.Company)
class CompanyAdmin(VersionAdmin):
    """Admin for Company"""

    model = models.Company
    search_fields = ["name"]
    list_display = ["name"]
    list_filter = ["name"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "name",
                ]
            },
        ),
    ]
