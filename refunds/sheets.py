"""Google Sheets integration for refunds."""

import logging

log = logging.getLogger(__name__)


def update_google_sheets(refund_id):
    """Update the Google Sheet with the refund information."""

    log.debug("update_google_sheets called: %s", refund_id)
