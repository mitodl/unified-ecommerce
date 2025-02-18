"""Celery tasks for refunds."""

import logging

from unified_ecommerce.celery import app

log = logging.getLogger(__name__)


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
def queue_process_approved_refund(
    request_id: int, *, auto_approved: bool = False
) -> None:
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
        process_approved_refund(request, auto_approved=auto_approved)
    except Request.DoesNotExist:
        log.exception("%s: Request %s not found", __name__, request_id)
    except RefundRequestImproperStateError:
        log.exception("%s: Request %s in improper state", __name__, request_id)
    except RefundTransactionFailedError:
        log.exception("%s: Request %s transaction failed", __name__, request_id)
    except RefundOrderPaymentTypeUnsupportedError:
        log.exception(
            "%s: Request %s order is a PayPal order, can't process",
            __name__,
            request_id,
        )
