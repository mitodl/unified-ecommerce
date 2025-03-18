"""Celery tasks for refunds."""

import logging

from celery.exceptions import SoftTimeLimitExceeded
from mitol.google_sheets_refunds.api import RefundRequestHandler

from unified_ecommerce.celery import app

log = logging.getLogger(__name__)


@app.task(time_limit=120, soft_time_limit=60)
def process_google_sheets_requests():
    """Process refund requests from Google Sheets."""
    try:
        refund_request_handler = RefundRequestHandler()
        if refund_request_handler.is_configured():
            refund_request_handler.process_sheet()
        else:
            log.warning("Google Sheets refund requests not configured")
    except SoftTimeLimitExceeded:
        log.info("Google Sheets requests exceeded time limit")


@app.task
def queue_refund_access_code_emails(request_id: int, batch: str) -> None:
    """Queue up the emails for the refund request."""

    from requests.api import send_request_access_code_email
    from requests.models import Request

    try:
        request = Request.objects.get(pk=request_id)
        codes = request.process_code.objects.filter(
            request=request, batch_uuid=batch
        ).all()

        for code in codes:
            send_request_access_code_email(code)

    except Request.DoesNotExist:
        log.exception("%s: Request %s not found", __name__, request_id)
        return


@app.task
def queue_process_approved_refund(request_id: int, *, reraise: bool = False) -> None:
    """Queue up the processing for an approved refund request."""

    from refunds.api import process_approved_refund
    from refunds.exceptions import (
        RefundOrderPaymentTypeUnsupportedError,
        RefundRequestImproperStateError,
        RefundTransactionFailedError,
    )
    from refunds.models import Request

    try:
        request = Request.objects.get(pk=request_id)
        process_approved_refund(request)
    except Request.DoesNotExist:
        log.exception("%s: Request %s not found", __name__, request_id)
        # If we're processing from Google Sheets, we need to catch the exception
        # there too.
        if reraise:
            raise
    except RefundRequestImproperStateError:
        log.exception("%s: Request %s in improper state", __name__, request_id)
        if reraise:
            raise
    except RefundTransactionFailedError:
        log.exception("%s: Request %s transaction failed", __name__, request_id)
        if reraise:
            raise
    except RefundOrderPaymentTypeUnsupportedError:
        log.exception(
            "%s: Request %s order is a PayPal order, can't process",
            __name__,
            request_id,
        )
        if reraise:
            raise
