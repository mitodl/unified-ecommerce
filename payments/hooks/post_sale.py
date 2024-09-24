"""Post-sale hook implementations for payments."""

import logging

import pluggy
import requests

from payments.constants import PAYMENT_HOOK_ACTION_POST_SALE
from payments.models import Order
from payments.serializers.v0 import WebhookBase, WebhookBaseSerializer, WebhookOrder

hookimpl = pluggy.HookimplMarker("unified_ecommerce")


class PostSaleSendEmails:
    """Send email when the order is fulfilled."""

    @hookimpl
    def post_sale(self, order_id, source):
        """Send email when the order is fulfilled."""
        log = logging.getLogger(__name__)

        msg = "Sending email for order %s with source %s"
        log.info(msg, order_id, source)


class IntegratedSystemWebhooks:
    """Figures out what webhook endpoints to call, and calls them."""

    @hookimpl
    def post_sale(self, order_id, source):
        """Call the webhook endpoints for the order."""

        log = logging.getLogger(__name__)

        log.info(
            "Calling webhook endpoints for order %s with source %s", order_id, source
        )

        order = Order.objects.prefetch_related("lines", "lines__product_version").get(
            pk=order_id
        )

        systems = [
            product.system
            for product in [
                line.product_version._object_version.object  # noqa: SLF001
                for line in order.lines.all()
            ]
        ]

        for system in systems:
            system_webhook_url = system.webhook_url
            system_slug = system.slug
            if system_webhook_url:
                log.info(
                    ("Calling webhook endpoint %s for order %s with source %s"),
                    system_webhook_url,
                    order_id,
                    source,
                )

                order_info = WebhookOrder(
                    order=order,
                    lines=[
                        line
                        for line in order.lines.all()
                        if line.product.system.slug == system_slug
                    ],
                )

                webhook_data = WebhookBase(
                    type=PAYMENT_HOOK_ACTION_POST_SALE,
                    system_key=system.api_key,
                    user=order.purchaser,
                    data=order_info,
                )

                serializer = WebhookBaseSerializer(webhook_data)

                if serializer.is_valid():
                    requests.post(
                        system_webhook_url,
                        json=serializer.data,
                        timeout=30,
                    )
                else:
                    log.error("Webhook serializer invalid: %s", serializer.errors)
