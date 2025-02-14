"""Hookimpl to send processing codes for created refund requests."""

import logging
from decimal import Decimal

import pluggy

from unified_ecommerce.constants import REFUND_STATUS_CREATED

hookimpl = pluggy.HookimplMarker("unified_ecommerce")
log = logging.getLogger(__name__)


class RefundCreatedHooks:
    """Hookimpls for the refund created event."""

    def _resolve_refund_request(self, refund_id):
        """Resolve the refund request from the ID."""
        from refunds.models import Request

        request = Request.objects.filter(
            status=REFUND_STATUS_CREATED, pk=refund_id
        ).first()

        if not request:
            log.error(
                "refund_created hook _resolve_refund_request: request %s not found",
                refund_id,
            )

        return request

    @hookimpl(specname="refund_created")
    def send_processing_codes(self, refund_id):
        """
        Send processing codes for the refund request.

        Args:
        - refund_id (int): ID of the refund request.
        """
        from refunds.api import create_request_access_codes

        log.debug("refund_created hook send_processing_codes called: %s", refund_id)

        request = self._resolve_refund_request(refund_id)

        create_request_access_codes(request) if request else None

    @hookimpl(specname="refund_created")
    def update_google_sheets(self, refund_id):
        """Update the Google Sheet with the refund information."""

        log.debug("refund_created hook update_google_sheets called: %s", refund_id)

        request = self._resolve_refund_request(refund_id)

        return "created" if request else None

    @hookimpl(specname="refund_created", tryfirst=True)
    def auto_approve_refund(self, refund_id):
        """
        Automatically approve the refund request if the conditions are met.

        Refunds can be auto-approved if the refund is zero-value. This is also
        where we'll implement auto-approval rules in a future version of this.
        """
        from refunds.models import Request

        log.debug("refund_created hook auto_approve_refund called: %s", refund_id)
        request = Request.objects.get(pk=refund_id)

        if request.total_requested == Decimal(0):
            log.info(
                "refund_created auto_approve_refund: auto-approving %s (zero value)",
                request,
            )
            request.approve(
                "Auto-approved zero-value refund request.", auto_approved=True
            )
