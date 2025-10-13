"""Models for refund processing."""

import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from mitol.common.models import TimestampedModel

from payments.models import Line, Order, Transaction
from refunds.exceptions import RefundAlreadyCompleteError, RefundOrderImproperStateError
from refunds.tasks import queue_process_approved_refund
from system_meta.models import IntegratedSystem
from unified_ecommerce.constants import (
    REFUND_CODE_TYPE_CHOICES,
    REFUND_STATUS_APPROVED,
    REFUND_STATUS_CHOICES,
    REFUND_STATUS_CREATED,
    REFUND_STATUS_DENIED,
    REFUND_STATUSES_PROCESSABLE,
)
from unified_ecommerce.plugin_manager import get_plugin_manager

log = logging.getLogger(__name__)
pm = get_plugin_manager()


class RequestRecipient(TimestampedModel):
    """
    Stores recipients for refund request emails.

    Refund requests may be sent to an email address for processing. This may not
    be someone who has an account in the system - it could be a mailing list or
    generic support address (or helpdesk system).

    No direct FKs to this - the processing codes capture the email address so
    this list can change at will.
    """

    email = models.EmailField(help_text="The email address to send refund requests to.")
    integrated_system = models.ForeignKey(
        IntegratedSystem,
        on_delete=models.CASCADE,
        related_name="+",
    )

    def __str__(self):
        """Return a reasonable string representation of the recipient."""

        return f"{self.email} ({self.system.name})"

    class Meta:
        """Meta opts for the model."""

        unique_together = [["email", "integrated_system"]]


class Request(TimestampedModel):
    """Contains requests for refunds"""

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refund_requests",
    )
    # Allow for multiple requests for an order - there's potential for the request
    # to be declined, or for more than one request to be made for different lines.
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="refund_requests"
    )

    processed_date = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_refund_requests",
        null=True,
        blank=True,
        help_text="The user who processed the request. (Usually blank.)",
    )

    total_refunded = models.DecimalField(
        decimal_places=5,
        max_digits=20,
        default=Decimal(0),
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default=REFUND_STATUS_CREATED,
        blank=True,
    )

    zendesk_ticket = models.CharField(max_length=255, blank=True, default="")
    refund_reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason for refund, supplied by the processing user.",
    )

    @property
    def total_requested(self):
        """Return the total requested refund amount, pulled from the line items."""

        return Decimal(sum(line.line.total_price for line in self.lines.all()))

    @property
    def total_approved(self):
        """Return the total approved amount, pulled from the line items."""

        return Decimal(sum(line.refunded_amount for line in self.lines.all()))

    def _check_status_prerequisites(self):
        """
        Check the request and the order before refunding it.

        Regardless of whether this is an approval or a denial, we should check
        if the order is in a proper state to be refunded, and whether or not
        the request itself is in a proper state for processing.
        """

        if self.status not in REFUND_STATUSES_PROCESSABLE:
            msg = f"Request {self} must be in a processable state to process."
            raise RefundAlreadyCompleteError(msg)

        if self.order.state != Order.STATE.FULFILLED:
            msg = (
                f"Order {self.order.reference_number} must be in fulfilled "
                "state to process."
            )
            raise RefundOrderImproperStateError(msg)

    def approve(
        self,
        reason: str,
        *,
        lines: list | None = None,
        skip_process_delay: bool = False,
    ):
        """
        Approve the request.

        Set the request status and the appropriate lines to "approved", then
        queue a task to process the refund via CyberSource.
        """

        self._check_status_prerequisites()

        self.refund_reason = reason
        self.status = REFUND_STATUS_APPROVED
        self.save()

        if lines:
            for line in lines:
                self.lines.filter(pk=line["line"]).update(
                    status=REFUND_STATUS_APPROVED,
                    refunded_amount=line["refunded_amount"],
                )
        else:
            for line in self.lines.all():
                # total_price is a calculated field, can't use an F object
                line.status = REFUND_STATUS_APPROVED
                line.refunded_amount = line.line.total_price
                line.save()

        if skip_process_delay:
            # If we're processing a refund from Google Sheets, we don't want to
            # delay the transaction, since we need to write back to the sheet
            # if it fails or succeeds.
            log.debug("Running refund processing for request %s", self.pk)
            queue_process_approved_refund(self.pk, reraise=True)
        else:
            log.debug("Queueing refund processing for request %s", self.pk)
            queue_process_approved_refund.delay(self.pk)

    def deny(self, reason: str):
        """Deny the request."""

        self._check_status_prerequisites()

        self.status = REFUND_STATUS_DENIED
        self.refund_reason = reason
        self.save()
        self.lines.update(status=REFUND_STATUS_DENIED)

        pm.hook.refund_denied(refund_id=self.pk)

    def __str__(self):
        """Return a reasonable string representation of the request."""

        return (
            f"{self.status} request for order {self.order.reference_number}:"
            f" {self.total_requested} requested {self.total_refunded} refunded"
        )


class RequestProcessingCode(TimestampedModel):
    """
    Stores codes for approving/denying a request.

    These will get sent to anyone with a flag set in their profile, and this
    allows a unique set of codes to be sent to each, tracked, and expired.
    """

    refund_request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="process_code"
    )

    email = models.EmailField(help_text="The email address the code was sent to.")

    code_batch = models.UUIDField(
        blank=True,
        null=True,
        help_text="Batch ID, generated when the codes are generated.",
    )
    approve_code = models.UUIDField(default=uuid.uuid4, editable=False)
    deny_code = models.UUIDField(default=uuid.uuid4, editable=False)

    code_active = models.BooleanField(default=True)
    code_used = models.CharField(
        choices=REFUND_CODE_TYPE_CHOICES,
        max_length=20,
        default="",
        blank=True,
    )
    code_used_on = models.DateTimeField(null=True, blank=True)


class RequestLine(TimestampedModel):
    """Line items for a refund request."""

    refund_request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="lines"
    )
    line = models.ForeignKey(
        Line,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="The individual line item to refund.",
    )
    status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default=REFUND_STATUS_CREATED,
        blank=True,
        help_text="The status of this line item.",
    )
    refunded_amount = models.DecimalField(
        decimal_places=5,
        max_digits=20,
        default=Decimal(0),
        blank=True,
        null=True,
        help_text=(
            "The amount refunded for this line item "
            "(may not be the full amount charged)."
        ),
    )
    transactions = models.ManyToManyField(
        Transaction,
        related_name="refund_request_lines",
        blank=True,
    )
