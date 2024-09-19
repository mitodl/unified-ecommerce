"""Post-sale hook implementations for payments."""

import logging

import pluggy
import requests

from payments.models import Order
from payments.serializers.v0 import WebhookOrderDataSerializer

hookimpl = pluggy.HookimplMarker("unified_ecommerce")


class PostSaleSendEmails:
    """Send email when the order is fulfilled."""

    @hookimpl
    def post_sale(self, order_id, source):
        """Send email when the order is fulfilled."""
        log = logging.getLogger(__name__)

        msg = f"Sending email for order {order_id} with source {source}"
        log.info(msg)


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
            system_webhook_url = system.sale_succeeded_webhook_url
            system_slug = system.slug
            if system_webhook_url:
                log.info(
                    ("Calling webhook endpoint %s for order %s with source %s"),
                    system_webhook_url,
                    order_id,
                    source,
                )

                serialized_data = WebhookOrderDataSerializer(
                    {
                        "order_id": order_id,
                        "system_slug": system_slug,
                        "action": "postsale",
                    }
                ).data
                requests.post(
                    system_webhook_url,
                    json=serialized_data,
                    timeout=30,
                )
