"""Tasks for the payments app."""

import logging

import requests
from django.conf import settings

from payments.constants import PAYMENT_HOOK_ACTION_POST_SALE
from payments.serializers.v0 import WebhookBase, WebhookBaseSerializer, WebhookOrder
from unified_ecommerce.celery import app

log = logging.getLogger(__name__)


@app.task()
def send_post_sale_webhook(system, order, source, attempt_count=0):
    """
    Actually send the webhook some data for a post-sale event.

    This is split out so we can queue the webhook requests individually.
    """

    system_webhook_url = system.webhook_url
    if system_webhook_url:
        log.info(
            ("Calling webhook endpoint %s for order %s with source %s"),
            system_webhook_url,
            order.reference_number,
            source,
        )

    order_info = WebhookOrder(
        order=order,
        lines=[
            line
            for line in order.lines.all()
            if line.product.system.slug == system.slug
        ],
    )

    webhook_data = WebhookBase(
        type=PAYMENT_HOOK_ACTION_POST_SALE,
        system_key=system.api_key,
        user=order.purchaser,
        data=order_info,
    )

    serializer = WebhookBaseSerializer(webhook_data)

    try:
        requests.post(
            system_webhook_url,
            json=serializer.data,
            timeout=30,
        )
    except (requests.Timeout, requests.HTTPError, requests.ConnectionError) as e:
        # These may indicate an issue on the integrated system end, so we'll
        # delay it for a while and retry, as long as it isn't too many times.

        log.warning(
            (
                "Had problems getting to the webhook URL %s on attempt %s for "
                "order %s for system %s: %s"
            ),
            system_webhook_url,
            attempt_count,
            order.reference_number,
            system.slug,
            e,
        )

        attempt_count += 1

        if attempt_count == settings.MITOL_UE_WEBHOOK_RETRY_MAX:
            log.exception(
                (
                    "Hit the retry max (%s) for webhook URL %s for order %s for "
                    "system %s, giving up"
                ),
                attempt_count,
                order.reference_number,
                system.slug,
                exc_info=e,
            )
            return

        send_post_sale_webhook.s(system, order, source, attempt_count).apply_async(
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
            (
                "Webhook URL %s for system %s in order %s returned something "
                "unexpected: %s"
            ),
            system_webhook_url,
            system.slug,
            order.reference_number,
            exc_info=e,
        )
    except requests.RequestException as e:
        # Some other error happened.

        log.exception(
            (
                "Unexpected error trying to dispatch to webhook URL %s for "
                "system %s in order %s returned something unexpected: %s"
            ),
            system_webhook_url,
            system.slug,
            order.reference_number,
            exc_info=e,
        )
