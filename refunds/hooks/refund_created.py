"""Hookimpl to send processing codes for created refund requests."""

import logging

import pluggy

hookimpl = pluggy.HookimplMarker("unified_ecommerce")
log = logging.getLogger(__name__)


class RefundCreatedHooks:
    """Hookimpls for the refund created event."""

    @hookimpl(specname="refund_created")
    def send_processing_codes(self, refund_id):
        """
        Send processing codes for the refund request.

        Args:
        - refund_id (int): ID of the refund request.
        """
        from refunds.api import create_request_access_codes
        from refunds.models import Request

        log.debug("refund_created hook send_processing_codes called: %s", refund_id)

        request = Request.objects.get(pk=refund_id)
        create_request_access_codes(request)

    @hookimpl(specname="refund_created")
    def update_google_sheets(self, refund_id):
        """Update the Google Sheet with the refund information."""

        log.debug("refund_created hook update_google_sheets called: %s", refund_id)
