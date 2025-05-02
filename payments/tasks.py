"""Tasks for the payments app."""

import logging

import requests
from django.conf import settings

from payments.mail_api import send_successful_order_payment_email
from payments.serializers.v0 import WebhookBase
from unified_ecommerce.celery import app

log = logging.getLogger(__name__)


@app.task
def successful_order_payment_email_task(order_id, email_subject, email_body):
    """Send order success email."""

    from payments.models import Order

    order = Order.objects.get(id=order_id)
    send_successful_order_payment_email(order, email_subject, email_body)


@app.task()
def dispatch_webhook(system_webhook_url, webhook_data, attempt_count=0):
    """Dispatch a webhook."""

    webhook_dataclass = WebhookBase(**webhook_data)

    try:
        requests.post(
            system_webhook_url,
            json=webhook_data,
            timeout=30,
        )
    except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
        # These may indicate an issue on the integrated system end, so we'll
        # delay it for a while and retry, as long as it isn't too many times.

        log.warning(
            (
                "Had problems getting to the webhook URL %s on attempt %s for "
                "event %s: %s"
            ),
            system_webhook_url,
            attempt_count,
            webhook_dataclass,
            e,
        )

        attempt_count += 1

        if attempt_count == settings.MITOL_UE_WEBHOOK_RETRY_MAX:
            log.exception(
                ("Hit the retry max (%s) for webhook URL %s for event %s, giving up"),
                attempt_count,
                webhook_dataclass,
                exc_info=e,
            )
            return

        log.info(
            "Requeueing post-sale webhook %s for event %s",
            system_webhook_url,
            webhook_dataclass,
        )
        dispatch_webhook.s(system_webhook_url, webhook_data, attempt_count).apply_async(
            countdown=settings.MITOL_UE_WEBHOOK_RETRY_COOLDOWN
        )
    except (
        requests.URLRequired,
        requests.TooManyRedirects,
        requests.JSONDecodeError,
    ) as e:
        # These may indicate that the webhook URL is wrong - it's either not set
        # or set to something that is returning gibberish, so don't retry.

        log.exception(
            ("Webhook URL %s for event %s returned something unexpected: %s"),
            system_webhook_url,
            webhook_dataclass,
            exc_info=e,
        )
    except requests.RequestException as e:
        # Some other error happened.

        log.exception(
            (
                "Unexpected error trying to dispatch to webhook URL %s for "
                "event %s returned something unexpected: %s"
            ),
            system_webhook_url,
            webhook_dataclass,
            exc_info=e,
        )
