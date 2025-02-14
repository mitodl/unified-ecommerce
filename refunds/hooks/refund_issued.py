"""Hookimpls to be called when refunds are issued."""

import logging

import pluggy

hookimpl = pluggy.HookimplMarker("unified_ecommerce")
log = logging.getLogger(__name__)


class RefundIssuedHooks:
    """Hookimpls for the refund created event."""

    @hookimpl(specname="refund_issued")
    def send_approval_email(self, refund_id):
        """
        Send denial email for the refund request.

        Args:
        - refund_id (int): ID of the refund request.
        """

        from refunds.mail_api import send_refund_issued_email

        log.debug("refund_issued hook send_approval_email called: %s", refund_id)
        send_refund_issued_email(refund_id)

    @hookimpl(specname="refund_issued")
    def update_google_sheets(self, refund_id):
        """Update the Google Sheet with the refund information."""

        from refunds.sheets import update_google_sheets

        log.debug("refund_issued hook update_google_sheets called: %s", refund_id)
        update_google_sheets(refund_id)
