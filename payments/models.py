"""Models for payment processing."""
# ruff: noqa: TD002,TD003,FIX002

import logging
import re
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.functional import cached_property
from mitol.common.models import TimestampedModel
from payments.tasks import successful_order_payment_email_task
from reversion.models import Version

from system_meta.models import Product
from unified_ecommerce.constants import (
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
    TRANSACTION_TYPES,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class Basket(TimestampedModel):
    """Represents a User's basket."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="basket")

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

        all_items_found = self.basket_items.count() == order.lines.count()

        if all_items_found:
            for basket_item in self.basket_items.all():
                for order_item in order.lines.all():
                    if order_item.product != basket_item.product:
                        all_items_found = False

        return all_items_found

    def get_products(self):
        """
        Return the products that have been added to the basket so far.
        """

        return [item.product for item in self.basket_items.all()]

    @staticmethod
    def establish_basket(request):
        """
        Get or create the user's basket.

        Args:
        request (HttpRequest): The HTTP request.
        system (IntegratedSystem): The system to associate with the basket.
        """
        user = request.user
        (basket, is_new) = Basket.objects.filter(user=user).get_or_create(
            defaults={"user": user}
        )

        if is_new:
            basket.save()

        return basket


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
    def discounted_price(self):
        """
        Return the price of the product with discounts.

        TODO: we don't have discounts yet, so this needs to be filled out when we do.
        """
        return self.base_price

    @cached_property
    def base_price(self):
        """Return the total price of the basket item without discounts."""
        return self.product.price * self.quantity


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
    total_price_paid = models.DecimalField(
        decimal_places=5,
        max_digits=20,
    )
    reference_number = models.CharField(max_length=255, default="", blank=True)

    # override save method to auto-fill generated_rerefence_number
    def save(self, *args, **kwargs):
        """Save the order."""

        logger.info("Saving order %s", self.id)

        # initial save in order to get primary key for new order
        super().save(*args, **kwargs)

        # can't insert twice because it'll try to insert with a PK now
        kwargs.pop("force_insert", None)

        # if we don't have a generated reference number, we generate one and save again
        if self.reference_number is None or len(self.reference_number) == 0:
            logger.info("Generating reference number for order %s", self.id)
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

    def fulfill(self, payment_data):
        """Fufill the order."""
        # record the transaction
        try:
            self.create_transaction(payment_data)

            # trigger post-sale events
            transaction.on_commit(self.handle_post_sale)

            # send the receipt emails
            transaction.on_commit(self.send_ecommerce_order_receipt)

            self.state = Order.STATE.FULFILLED
            self.save()
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
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

    def handle_post_sale(self):
        """
        Trigger post-sale events. This is where we used to have the logic to create
        courseruns enrollments and stuff.

        TODO: this should be implemented using Pluggy to figure out what to send back
        to the connected system.
        """

    def send_ecommerce_order_receipt(self):
        """
        Send the receipt email.
        """
        successful_order_payment_email_task(self.id, "Successful Order Payment",
                                            "Your payment has been successfully processed.")  # noqa: E501


class PendingOrder(Order):
    """An order that is pending payment"""

    @transaction.atomic
    def _get_or_create(self, products: list[Product], user: User):
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
            # Get the details from each Product.
            product_versions = [
                Version.objects.get_for_object(product).first() for product in products
            ]

            # Get or create a PendingOrder
            # TODO: we prefetched the discounts here
            orders = Order.objects.select_for_update().filter(
                lines__product_version__in=product_versions,
                state=Order.STATE.PENDING,
                purchaser=user,
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
                    purchaser=user,
                    total_price_paid=0,
                )

            # TODO: Apply any discounts to the PendingOrder

            # Create or get Line for each product.
            # Calculate the Order total based on Lines and discount.
            total = 0
            for i, _ in enumerate(products):
                line, _ = order.lines.get_or_create(
                    order=order,
                    defaults={
                        "product_version": product_versions[i],
                        "quantity": 1,
                    },
                )
                total += line.discounted_price

            order.total_price_paid = total

        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            order.state = Order.STATE.ERRORED

        order.save()

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
        return cls._get_or_create(cls, products, basket.user)

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

    class Meta:
        """Model meta options."""

        proxy = True


class ErroredOrder(Order):
    """
    An order that is errored.

    The state of this can't be altered further.
    """

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

    class Meta:
        """Model meta options."""

        constraints = [
            models.UniqueConstraint(
                fields=["order_id", "product_version_id"],
                name="unique_order_purchased_object",
            )
        ]

    @property
    def item_description(self):
        """Return the item description"""
        return self.product_version.field_dict["description"]

    @property
    def unit_price(self):
        """Return the price of the product"""
        return self.product_version.field_dict["price"]

    @cached_property
    def total_price(self):
        """Return the price of the product"""
        return self.unit_price * self.quantity

    @cached_property
    def discounted_price(self):
        """Return the price of the product with discounts"""
        return self.total_price

    @cached_property
    def product(self):
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
