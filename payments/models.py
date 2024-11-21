"""Models for payment processing."""
# ruff: noqa: TD002,TD003,FIX002

import logging
import re
import uuid
from datetime import datetime
from decimal import Decimal

import pytz
import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.functional import cached_property
from django_countries.fields import CountryField
from mitol.common.models import TimestampedModel
from mitol.payment_gateway.payment_utils import quantize_decimal
from reversion.models import Version
from safedelete.managers import SafeDeleteManager
from safedelete.models import SafeDeleteModel

from payments.constants import GEOLOCATION_CHOICES, GEOLOCATION_TYPE_NONE
from payments.utils import product_price_with_discount
from system_meta.models import IntegratedSystem, Product
from unified_ecommerce.constants import (
    DISCOUNT_TYPES,
    PAYMENT_TYPES,
    POST_SALE_SOURCE_REDIRECT,
    REDEMPTION_TYPES,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
    TRANSACTION_TYPES,
)
from unified_ecommerce.plugin_manager import get_plugin_manager
from unified_ecommerce.utils import SoftDeleteActiveModel

User = get_user_model()
log = logging.getLogger(__name__)
pm = get_plugin_manager()

class Company(TimestampedModel):
    """Company model"""

    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        """Return the company as a string."""

        return self.name

@reversion.register(exclude=("created_on", "updated_on"))
class Discount(TimestampedModel):
    """Discount model"""

    amount = models.DecimalField(
        decimal_places=2,
        max_digits=20,
    )
    automatic = models.BooleanField(default=False)
    discount_type = models.CharField(choices=DISCOUNT_TYPES, max_length=30)
    redemption_type = models.CharField(choices=REDEMPTION_TYPES, max_length=30)
    payment_type = models.CharField(null=True, choices=PAYMENT_TYPES, max_length=30)  # noqa: DJ001
    max_redemptions = models.PositiveIntegerField(null=True, default=0)
    discount_code = models.CharField(max_length=100, unique=True)
    activation_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, this discount code will not be redeemable before this date.",
    )
    expiration_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, this discount code will not be redeemable after this date.",
    )
    is_bulk = models.BooleanField(default=False)
    integrated_system = models.ForeignKey(
        IntegratedSystem,
        on_delete=models.PROTECT,
        related_name="discounts",
        blank=True,
        null=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="discounts",
        blank=True,
        null=True,
    )
    assigned_users = models.ManyToManyField(
        User,
        related_name="discounts",
        blank=True,
        null=True,
    )
    bulk_discount_collection = models.ForeignKey(
        "BulkDiscountCollection",
        on_delete=models.PROTECT,
        related_name="discounts",
        blank=True,
        null=True,
    )
    transaction_number = models.CharField(
        max_length=255,
        blank=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="discounts",
        blank=True,
        null=True,
    )

    def is_valid(self, basket) -> bool:
        """
        Check if the discount is valid for the basket.

        Args:
            basket (Basket): The basket to check the discount against.
        Returns:
            bool: True if the discount is valid for the basket, False otherwise.

        """

        def _discount_product_in_basket() -> bool:
            """
            Check if the discount is associated to the product in the basket.

            Returns:
                bool: True if the discount is associated to the product in the basket,
                or not associated with any product.
            """
            return self.product is None or self.product in basket.get_products()

        def _discount_user_has_discount() -> bool:
            """
            Check if the discount is associated with the basket's user.

            Returns:
                bool: True if the discount is associated with the basket's user,
                or not associated with any user.
            """
            return self.assigned_users.count() == 0 or self.assigned_users.contains(
                basket.user
            )

        def _discount_redemption_limit_valid() -> bool:
            """
            Check if the discount has been redeemed less than the maximum number
            of times.

            Returns:
                bool: True if the discount has been redeemed less than the maximum
                number of times, or the maximum number of redemptions is 0.
            """
            return (
                self.max_redemptions == 0
                or self.redeemed_discounts.count() < self.max_redemptions
            )

        def _discount_activation_date_valid() -> bool:
            """
            Check if the discount's activation date is in the past.

            Returns:
                bool: True if the discount's activation date is in the past, or the
                activation date is None.
            """
            now = datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
            return self.activation_date is None or now >= self.activation_date

        def _discount_expiration_date_valid() -> bool:
            """
            Check if the discount's expiration date is in the future.

            Returns:
                bool: True if the discount's expiration date is in the future, or the
                expiration date is None.
            """
            now = datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
            return self.expiration_date is None or now <= self.expiration_date

        def _discount_integrated_system_found_in_basket_or_none() -> bool:
            """
            Check if the discount's integrated system is the same as the basket's
            integrated system.
            Returns:
                bool: True if the discount's integrated system is the same as the
                basket's integrated system, or the discount's integrated system is None.
            """
            return (
                self.integrated_system is None
                or self.integrated_system == basket.integrated_system
            )

        return (
            _discount_product_in_basket()
            and _discount_user_has_discount()
            and _discount_redemption_limit_valid()
            and _discount_activation_date_valid()
            and _discount_expiration_date_valid()
            and _discount_integrated_system_found_in_basket_or_none()
        )

    def __str__(self):
        """Return the discount as a string."""

        return f"{self.amount} {self.discount_type} {self.redemption_type} - {self.discount_code}"  # noqa: E501

    @staticmethod
    def resolve_discount_version(discount, discount_version=None):
        """
        Resolve the specified version of the discount. Specify None to indicate the
        current version.

        Returns: Discount; either the discount you passed in or the version of the
        discount you requested.
        """
        if discount_version is None:
            return discount

        versions = reversion.models.Version.objects.get_for_object(discount)

        if versions.count() == 0:
            return discount

        for test_version in versions.all():
            if test_version == discount_version:
                return Discount(
                    id=test_version.field_dict["id"],
                    amount=test_version.field_dict["amount"],
                    automatic=test_version.field_dict["automatic"],
                    discount_type=test_version.field_dict["discount_type"],
                    redemption_type=test_version.field_dict["redemption_type"],
                    payment_type=test_version.field_dict["payment_type"],
                    max_redemptions=test_version.field_dict["max_redemptions"],
                    discount_code=test_version.field_dict["discount_code"],
                    activation_date=test_version.field_dict["activation_date"],
                    expiration_date=test_version.field_dict["expiration_date"],
                    is_bulk=test_version.field_dict["is_bulk"],
                    integrated_system=IntegratedSystem.objects.get(
                        pk=test_version.field_dict["integrated_system_id"]
                    ),
                    product=Product.objects.get(
                        pk=test_version.field_dict["product_id"]
                    ),
                    assigned_users=test_version.field_dict["assigned_users"],
                    deleted_on=test_version.field_dict["deleted_on"],
                    deleted_by_cascade=test_version.field_dict["deleted_by_cascade"],
                )
        exception_message = "Invalid product version specified"
        raise TypeError(exception_message)
    class Meta:
        """Model meta options."""

        indexes = [
            models.Index(fields=["company"]),
        ]


class BulkDiscountCollection(TimestampedModel):
    """Bulk Discount Collection model"""

    prefix = models.CharField(max_length=100, unique=True)


class BlockedCountry(SafeDeleteModel, SoftDeleteActiveModel, TimestampedModel):
    """
    Represents a country that is blocked from purchasing.

    This can either be for a particular product, or a system-wide block.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="blocked_countries",
        null=True,
        blank=True,
        default=None,
    )
    country_code = CountryField()

    objects = SafeDeleteManager()
    all_objects = models.Manager()

    class Meta:
        """Meta options for the model"""

        verbose_name_plural = "blocked countries"
        unique_together = ("product", "country_code")

    def __str__(self):
        """Return model data as a string"""

        return (
            f"product='{self.product.sku if self.product else 'global'}';"
            f" country='{self.country_code.name}'"
        )


class TaxRate(SafeDeleteModel, SoftDeleteActiveModel, TimestampedModel):
    """
    Stores tax rates for countries. Generally, this should be a VAT rate, but
    a text field is supplied to store the name of the tax assessed
    """

    country_code = CountryField()
    tax_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    tax_rate_name = models.CharField(max_length=100, blank=True, default="VAT")

    objects = SafeDeleteManager()
    all_objects = models.Manager()

    class Meta:
        """Meta options for the model"""

        constraints = [
            models.UniqueConstraint(fields=["country_code"], name="unique_country")
        ]

    def to_dict(self):
        """Return object data as dict"""

        return {
            "country_code": self.country_code,
            "tax_rate": self.tax_rate,
            "tax_rate_name": self.tax_rate_name,
            "active": self.active,
        }

    def __str__(self):
        """Return model data as a string"""

        return f"{self.tax_rate}% {self.tax_rate_name} for {self.country_code}"


class Basket(TimestampedModel):
    """Represents a User's basket."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="basket")
    integrated_system = models.ForeignKey(
        IntegratedSystem, on_delete=models.CASCADE, related_name="basket"
    )
    discounts = models.ManyToManyField(Discount, related_name="basket")
    user_ip = models.CharField(
        blank=True, max_length=46, help_text="The IP address of the user."
    )
    user_taxable_country_code = models.CharField(  # noqa: DJ001
        max_length=2,
        help_text="The country code for the user for this basket for tax purposes.",
        blank=True,
        null=True,
        default="",
    )
    user_taxable_geolocation_type = models.CharField(
        default=GEOLOCATION_TYPE_NONE,
        choices=GEOLOCATION_CHOICES,
        help_text="How the user's location was determined for tax purposes.",
        max_length=15,
    )
    user_blockable_country_code = models.CharField(  # noqa: DJ001
        max_length=2,
        help_text="The country code for the user for this basket for blocked items.",
        blank=True,
        null=True,
        default="",
    )
    user_blockable_geolocation_type = models.CharField(
        default=GEOLOCATION_TYPE_NONE,
        choices=GEOLOCATION_CHOICES,
        help_text="How the user's location was determined for blocked items.",
        max_length=15,
    )
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.DO_NOTHING,
        related_name="+",
        help_text="The tax rate assessed for this basket.",
        null=True,
        blank=True,
    )

    def compare_to_order(self, order):
        """
        Compare this basket with the specified order. An order is considered
        equal to the basket if it meets these criteria:
        - Users match
        - Products match on each line
        - Discounts match
        """
        if self.user != order.purchaser:
            return False

        basket_products = {item.product for item in self.basket_items.all()}
        order_products = {line.product for line in order.lines.all()}

        return basket_products == order_products

    def get_products(self):
        """
        Return the products that have been added to the basket so far.
        """

        return [item.product for item in self.basket_items.all()]

    def set_customer_location(self, customer_location):
        """Ingest a CustomerLocationMetadata object."""

        self.user_ip = customer_location.location_block.ip

        self.user_blockable_country_code = customer_location.location_block.country_code
        self.user_blockable_geolocation_type = (
            customer_location.location_block.lookup_type
        )
        self.user_taxable_country_code = customer_location.location_tax.country_code
        self.user_taxable_geolocation_type = customer_location.location_tax.lookup_type

    @property
    def subtotal(self) -> Decimal:
        """Return the subtotal amount for the basket."""

        return Decimal(sum([item.discounted_price for item in self.basket_items.all()]))

    @property
    def tax(self) -> Decimal:
        """Return the aggregate tax for the basket."""

        return Decimal(sum([item.tax for item in self.basket_items.all()]))

    @property
    def total(self) -> Decimal:
        """Return the total for the basket, including discounts and tax."""

        return Decimal(sum([item.total_price for item in self.basket_items.all()]))

    @property
    def subtotal_money(self) -> Decimal:
        """Return the subtotal amount for the basket."""

        return quantize_decimal(self.subtotal)

    @property
    def tax_money(self) -> Decimal:
        """Return the aggregate tax for the basket."""

        return quantize_decimal(self.tax)

    @property
    def total_money(self) -> Decimal:
        """Return the total for the basket, including discounts and tax."""

        return quantize_decimal(self.total_money)

    @staticmethod
    def establish_basket(request, integrated_system: IntegratedSystem):
        """
        Get or create the user's basket.

        Args:
        request (HttpRequest): The HTTP request.
        system (IntegratedSystem): The system to associate with the basket.
        """
        user = request.user
        (basket, is_new) = Basket.objects.filter(
            user=user, integrated_system=integrated_system
        ).get_or_create(defaults={"user": user, "integrated_system": integrated_system})

        if is_new:
            basket.save()

        return basket

    def apply_discount_to_basket(self, discount: Discount):
        """
        Apply a discount to a basket.

        Args:
            discount (Discount): The Discount to apply to the basket.
        """
        if discount.is_valid(self):
            self.discounts.add(discount)
            self.save()

    constraints = [
        models.UniqueConstraint(
            fields=["user", "integrated_system"],
            name="unique_user_integrated_system",
        ),
    ]


class BasketItem(TimestampedModel):
    """Represents one or more products in a user's basket."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="basket_item"
    )
    basket = models.ForeignKey(
        Basket, on_delete=models.CASCADE, related_name="basket_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    @cached_property
    def discounted_price(self) -> Decimal:
        """
        Get the price of the basket item with applicable discounts.

        Returns:
            Decimal: The price of the basket item reduced by an applicable discount.
        """
        # Check if discounts exist
        # check if the discount is applicable to the product
        # check if the discount is applicable to the the product's integrated system
        # if discount doesn't have product or integrated system, apply it
        price_with_best_discount = self.product.price
        if self.best_discount_for_item_from_basket:
            price_with_best_discount = product_price_with_discount(
                self.best_discount_for_item_from_basket, self.product
            )
        return price_with_best_discount

    @cached_property
    def best_discount_for_item_from_basket(self) -> Discount:
        """
        Get the best discount from the basket

        Returns:
            Discount: The best discount, associated with the basket, for the basket
            item.
        """
        best_discount = None
        best_discount_price = self.product.price
        for discount in self.basket.discounts.all():
            if (discount.product is None or discount.product == self.product) and (
                discount.integrated_system is None
                or discount.integrated_system == self.basket.integrated_system
            ):
                discounted_price = product_price_with_discount(discount, self.product)
                if best_discount is None or discounted_price < best_discount_price:
                    best_discount = discount
                    best_discount_price = discounted_price
        return best_discount

    @cached_property
    def discounted_price_money(self) -> Decimal:
        """Return the total with discounts and assessed tax, as a Money object."""

        return quantize_decimal(self.discounted_price)

    @cached_property
    def tax(self) -> Decimal:
        """
        Return the total tax assessed for this basket item.

        This considers the discounted price, not the base price of the item.
        """

        return (
            self.discounted_price * (self.basket.tax_rate.tax_rate / 100)
            if self.basket.tax_rate
            else Decimal(0)
        )

    @property
    def tax_money(self) -> Decimal:
        """Return the tax amount as a Money object."""

        return quantize_decimal(self.tax)

    @property
    def base_price(self) -> Decimal:
        """Return the total price of the basket item without discounts."""
        return self.product.price * self.quantity

    @property
    def base_price_money(self) -> Decimal:
        """Return the total with discounts and assessed tax, as a Money object."""

        return quantize_decimal(self.base_price)

    @property
    def price(self) -> Decimal:
        """Return the total price of the basket item with discounts."""
        return self.discounted_price * self.quantity

    @property
    def price_money(self) -> Decimal:
        """Return the total with discounts, as a Money object."""

        return quantize_decimal(self.price)

    @property
    def total_price(self) -> Decimal:
        """Return the total with discounts and assessed tax."""

        return self.price + self.tax

    @property
    def total_price_money(self) -> Decimal:
        """Return the total with discounts and assessed tax, as a Money object."""

        return quantize_decimal(self.total_price)


class Order(TimestampedModel):
    """An order containing information for a purchase."""

    class STATE:
        """Possible states for an order."""

        PENDING = "pending"
        FULFILLED = "fulfilled"
        CANCELED = "canceled"
        DECLINED = "declined"
        ERRORED = "errored"
        REFUNDED = "refunded"
        REVIEW = "review"
        PARTIALLY_REFUNDED = "partially_refunded"

        choices = [
            (PENDING, "Pending"),
            (FULFILLED, "Fulfilled"),
            (CANCELED, "Canceled"),
            (REFUNDED, "Refunded"),
            (DECLINED, "Declined"),
            (ERRORED, "Errored"),
            (REVIEW, "Review"),
        ]

    state = models.CharField(default=STATE.PENDING, choices=STATE.choices)
    purchaser = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    purchaser_ip = models.CharField(
        blank=True, max_length=46, help_text="The IP address of the user."
    )
    purchaser_taxable_country_code = models.CharField(
        max_length=2,
        help_text="The country code for the user for this order for tax purposes.",
        blank=True,
        default="",
    )
    purchaser_taxable_geolocation_type = models.CharField(
        default=GEOLOCATION_TYPE_NONE,
        choices=GEOLOCATION_CHOICES,
        help_text="How the user's location was determined for tax purposes.",
        max_length=15,
    )
    purchaser_blockable_country_code = models.CharField(
        max_length=2,
        help_text="The country code for the user for this order for blocked items.",
        blank=True,
        default="",
    )
    purchaser_blockable_geolocation_type = models.CharField(
        default=GEOLOCATION_TYPE_NONE,
        choices=GEOLOCATION_CHOICES,
        help_text="How the user's location was determined for blocked items.",
        max_length=15,
    )
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.DO_NOTHING,
        related_name="+",
        help_text="The tax rate assessed for this order.",
        null=True,
        blank=True,
    )

    total_price_paid = models.DecimalField(
        decimal_places=5,
        max_digits=20,
    )
    reference_number = models.CharField(max_length=255, default="", blank=True)

    # override save method to auto-fill generated_rerefence_number
    def save(self, *args, **kwargs):
        """Save the order."""

        log.info("Saving order %s", self.id)

        # initial save in order to get primary key for new order
        super().save(*args, **kwargs)

        # can't insert twice because it'll try to insert with a PK now
        kwargs.pop("force_insert", None)

        # if we don't have a generated reference number, we generate one and save again
        if self.reference_number is None or len(self.reference_number) == 0:
            log.info("Generating reference number for order %s", self.id)
            self.reference_number = self._generate_reference_number()
            super().save(*args, **kwargs)

    # Flag to determine if the order is in review status - if it is, then
    # we need to not step on the basket that may or may not exist when it is
    # accepted
    @property
    def is_review(self):
        """Return if the order is in review status"""
        return self.state == Order.STATE.REVIEW

    @property
    def is_fulfilled(self):
        """Return if the order is fulfilled"""
        return self.state == Order.STATE.FULFILLED

    @property
    def tax(self):
        """Return the aggregated tax amount for this order"""

        return quantize_decimal(sum([line.tax for line in self.lines.all()]))

    @property
    def subtotal(self):
        """Return the aggregated subtotal for the order"""

        return quantize_decimal(sum([line.base_price for line in self.lines.all()]))

    @property
    def discounts_applied(self):
        """Return the aggregated discounts applied to the order"""

        return quantize_decimal(
            sum([line.base_price - line.discounted_price for line in self.lines.all()])
        )

    def fulfill(self, payment_data, source=POST_SALE_SOURCE_REDIRECT):
        """Fufill the order."""
        # record the transaction
        try:
            self.create_transaction(payment_data)

            self.state = Order.STATE.FULFILLED
            self.save()

            # trigger post-sale events
            self.handle_post_sale(source=source)

            self.state = Order.STATE.FULFILLED
            self.save()

            # send the receipt emails
            self.send_ecommerce_order_receipt()
        except Exception as e:  # pylint: disable=broad-except
            log.exception(
                "Error occurred fulfilling order %s", self.reference_number, exc_info=e
            )

            self.errored()

    def cancel(self):
        """Cancel this order"""
        self.state = Order.STATE.CANCELED
        self.save()

    def decline(self):
        """Decline this order"""
        self.state = Order.STATE.DECLINED
        self.save()

        return self

    def errored(self):
        """Error this order"""
        self.state = Order.STATE.ERRORED
        self.save()

    def refund(self, *, api_response_data, **kwargs):
        """Issue a refund"""
        raise NotImplementedError

    def _generate_reference_number(self):
        """Generate the order reference number"""
        return (
            f"{settings.MITOL_UE_REFERENCE_NUMBER_PREFIX}-"
            f"{settings.ENVIRONMENT}-{self.id}"
        )

    def __str__(self):
        """Generate a string representation of the order"""
        return (
            f"{self.state.capitalize()} Order for {self.purchaser.username}"
            f" ({self.purchaser.email})"
        )

    @staticmethod
    def decode_reference_number(refno):
        """Decode the reference number"""
        return re.sub(rf"^.*-{settings.ENVIRONMENT}-", "", refno)

    def create_transaction(self, payment_data):
        """
        Create the transaction record for the order. This contains payment
        processor-specific data.
        """
        try:
            transaction_id = payment_data.get("transaction_id")
            amount = payment_data.get("amount")
            # There are two use cases:
            # No payment required - no cybersource involved, so we need to generate
            # a UUID as transaction id
            # Payment STATE_ACCEPTED - there should always be transaction_id in payment
            # data, if not, throw ValidationError
            if amount == 0 and transaction_id is None:
                transaction_id = uuid.uuid1()
            elif transaction_id is None:
                exception_message = (
                    "Failed to record transaction: Missing transaction id"
                    " from payment API response"
                )
                raise ValidationError(exception_message)  # noqa: TRY301

            self.transactions.get_or_create(
                transaction_id=transaction_id,
                data=payment_data,
                amount=self.total_price_paid,
            )
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            self.errored()

    def handle_post_sale(self, source=POST_SALE_SOURCE_REDIRECT):
        """
        Trigger post-sale events. This is where we used to have the logic to create
        courseruns enrollments and stuff.
        """

        log.info("Running post-sale events")

        pm.hook.post_sale(order_id=self.id, source=source)

    def send_ecommerce_order_receipt(self):
        """
        Send the receipt email.

        TODO: add email
        """

    def delete_redeemed_discounts(self):
        """Delete redeemed discounts"""
        self.redeemed_discounts.all().delete()


class PendingOrder(Order):
    """An order that is pending payment"""

    @transaction.atomic
    def _get_or_create(self, basket: Basket):
        """
        Return a singleton PendingOrder for the given products and user.

        Args:
        - products (List[Product]): List of Products associated with the
            PendingOrder.
        - user (User): The user expected to be associated with the PendingOrder.
        - discounts (List[Discounts]): List of Discounts to apply to each Line
            associated with the order.
            (TODO: update when the discounts code is migrated.)

        Returns:
            PendingOrder: the retrieved or created PendingOrder.
        """
        try:
            products = basket.get_products()
            # Get the details from each Product.
            product_versions = [
                Version.objects.get_for_object(product).first() for product in products
            ]

            # Get or create a PendingOrder
            # TODO: we prefetched the discounts here
            orders = Order.objects.select_for_update().filter(
                lines__product_version__in=product_versions,
                state=Order.STATE.PENDING,
                purchaser=basket.user,
            )
            # Previously, multiple PendingOrders could be created for a single user
            # for the same product, if multiple exist, grab the first.
            if orders:
                order = orders.first()
                # TODO: this should clear discounts from the order here

                order.refresh_from_db()
            else:
                order = Order.objects.create(
                    state=Order.STATE.PENDING,
                    purchaser=basket.user,
                    total_price_paid=0,
                )

            # TODO: Apply any discounts to the PendingOrder

            # Manually set these so that we get updated data if it changes
            # (this re-uses a PendingOrder if it exists, so it might now be wrong)
            order.tax_rate = basket.tax_rate
            order.purchaser_ip = basket.user_ip
            order.purchaser_taxable_country_code = basket.user_taxable_country_code
            order.purchaser_taxable_geolocation_type = (
                basket.user_taxable_geolocation_type
            )
            order.purchaser_blockable_country_code = basket.user_blockable_country_code
            order.purchaser_blockable_geolocation_type = (
                basket.user_blockable_geolocation_type
            )
            order.save()

            # Create or get Line for each product.
            # Calculate the Order total based on Lines and discount.
            total = Decimal(0)
            used_discounts = []
            for product_version in product_versions:
                basket_item = basket.basket_items.get(
                    product=product_version.field_dict["id"]
                )
                line, created = order.lines.get_or_create(
                    order=order,
                    product_version=product_version,
                    defaults={
                        "quantity": 1,
                        "discounted_price": basket_item.discounted_price,
                    },
                )
                used_discounts.append(basket_item.best_discount_for_item_from_basket)
                total += line.total_price_money
                log.debug(
                    "%s line %s product %s",
                    ("Created" if created else "Updated"),
                    line,
                    product_version.field_dict["sku"],
                )
                line.save()

            order.total_price_paid = total

        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            order.state = Order.STATE.ERRORED

        order.save()

        # delete unused discounts from basket
        for discount in basket.discounts.all():
            if discount not in used_discounts:
                basket.discounts.remove(discount)

        return order

    @classmethod
    def create_from_basket(cls, basket: Basket):
        """
        Create a new pending order from a basket

        Args:
            basket (Basket):  the user's basket to create an order for

        Returns:
            PendingOrder: the created pending order
        """
        products = basket.get_products()

        log.debug("Products to add to order: %s", products)

        order = cls._get_or_create(cls, basket)

        for discount in basket.discounts.all():
            RedeemedDiscount.objects.create(
                discount=discount,
                order=order,
                user=basket.user,
            )

        return order

    @classmethod
    def create_from_product(cls, product: Product, user: User):
        """
        Create a new pending order from a product

        Args:
        - product (Product): the product to create an order for
        - user (User): the user to create an order for
        - discount (Discount): the discount code to create an order discount redemption

        Returns:
            PendingOrder: the created pending order
        """

        return cls._get_or_create(cls, [product], user)

    class Meta:
        """Model meta options"""

        proxy = True


class FulfilledOrder(Order):
    """An order that has a fulfilled payment"""

    def refund(self, *, api_response_data: dict | None = None, **kwargs):
        """
        Record the refund, then trigger any post-refund events.

        Args:
        - api_response_data (dict|None): Response from the payment gateway for the
            refund, if any

        Keyword Args:
        - amount: amount that was refunded
        - reason:  reason for refunding the order

        Returns:
        - Object (Transaction): the refund transaction object for the refund.
        """
        try:
            amount = kwargs.get("amount")
            reason = kwargs.get("reason")

            transaction_id = api_response_data.get("id")
            if transaction_id is None:
                exception_message = (
                    "Failed to record transaction: Missing transaction id"
                    " from refund API response"
                )
                raise ValidationError(exception_message)  # noqa: TRY301

            refund_transaction, _ = self.transactions.get_or_create(
                transaction_id=transaction_id,
                data=api_response_data,
                amount=amount,
                transaction_type=TRANSACTION_TYPE_REFUND,
                reason=reason,
            )
            self.state = Order.STATE.REFUNDED
            self.save()

            # TODO: send_order_refund_email.delay(self.id)
            # (and any other post-refund events)

            return refund_transaction  # noqa: TRY300
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            self.errored()

    class Meta:
        """Model meta options."""

        proxy = True


class ReviewOrder(Order):
    """An order that has been placed under review by the payment processor."""

    class Meta:
        """Model meta options."""

        proxy = True


class CanceledOrder(Order):
    """
    An order that is canceled.

    The state of this can't be altered further.
    """

    def __init__(self):
        """Initialize the cancelled order."""

        self.delete_redeemed_discounts()

    class Meta:
        """Model meta options."""

        proxy = True


class RefundedOrder(Order):
    """
    An order that is refunded.

    The state of this can't be altered further.
    """

    class Meta:
        """Model meta options."""

        proxy = True


class DeclinedOrder(Order):
    """
    An order that is declined.

    The state of this can't be altered further.
    """

    def __init__(self):
        """Initialize the cancelled order."""

        self.delete_redeemed_discounts()

    class Meta:
        """Model meta options."""

        proxy = True


class ErroredOrder(Order):
    """
    An order that is errored.

    The state of this can't be altered further.
    """

    def __init__(self):
        """Initialize the cancelled order."""

        self.delete_redeemed_discounts()

    class Meta:
        """Model meta options."""

        proxy = True


class PartiallyRefundedOrder(Order):
    """
    An order that is partially refunded.

    The state of this can't be altered further.
    """

    class Meta:
        """Model meta options."""

        proxy = True


class Line(TimestampedModel):
    """A line in an Order."""

    def _order_line_product_versions():
        """Return a Q object filtering to Versions for Products"""
        return models.Q()

    order = models.ForeignKey(
        "payments.Order",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product_version = models.ForeignKey(
        Version,
        limit_choices_to=_order_line_product_versions,
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField()
    discounted_price = models.DecimalField(
        decimal_places=2,
        max_digits=20,
    )

    class Meta:
        """Model meta options."""

        constraints = [
            models.UniqueConstraint(
                fields=["order_id", "product_version_id"],
                name="unique_order_purchased_object",
            )
        ]

    @property
    def item_description(self) -> str:
        """Return the item description"""
        return self.product_version.field_dict["description"]

    @cached_property
    def unit_price(self) -> Decimal:
        """Return the price of the product"""
        return self.product_version.field_dict["price"]

    @cached_property
    def base_price(self) -> Decimal:
        """Return the price of the product"""
        return self.unit_price * self.quantity

    @cached_property
    def tax(self) -> Decimal:
        """Return the tax assessed for the item"""
        return (
            (self.base_price * (self.order.tax_rate.tax_rate) / 100)
            if self.order.tax_rate
            else 0
        )

    @cached_property
    def total_price(self) -> Decimal:
        """Return the price of the product"""
        return self.unit_price * self.quantity + self.tax

    @cached_property
    def unit_price_money(self) -> Decimal:
        """Return the price of the product"""
        return quantize_decimal(self.unit_price)

    @cached_property
    def tax_money(self) -> Decimal:
        """Return the tax assessed, as Money"""
        return quantize_decimal(self.tax)

    @cached_property
    def base_price_money(self) -> Decimal:
        """Return the price of the product"""
        return quantize_decimal(self.base_price)

    @cached_property
    def total_price_money(self) -> Decimal:
        """Return the price of the product"""
        return quantize_decimal(self.total_price)

    @cached_property
    def product(self) -> Product:
        """Return the product associated with the line"""
        return Product.resolve_product_version(
            Product.all_objects.get(pk=self.product_version.field_dict["id"]),
            self.product_version,
        )

    def __str__(self):
        """Return string version of the line."""
        return f"{self.product_version}"


class Transaction(TimestampedModel):
    """A transaction on an order, generally a payment but can also cover refunds"""

    # Per CyberSourse, Request ID should be 22 digits
    transaction_id = models.CharField(max_length=255, unique=True)

    order = models.ForeignKey(
        "payments.Order", on_delete=models.CASCADE, related_name="transactions"
    )
    amount = models.DecimalField(
        decimal_places=5,
        max_digits=20,
    )
    data = models.JSONField()
    transaction_type = models.TextField(
        choices=TRANSACTION_TYPES,
        default=TRANSACTION_TYPE_PAYMENT,
        null=False,
        max_length=20,
    )
    reason = models.CharField(max_length=255, blank=True)


class RedeemedDiscount(TimestampedModel):
    """Redeemed Discount model"""

    discount = models.ForeignKey(
        Discount, on_delete=models.PROTECT, related_name="redeemed_discounts"
    )
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="redeemed_discounts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="redeemed_discounts",
    )

    def __str__(self):
        """Return the redeemed discount as a string."""

        return f"{self.discount} {self.user}"
