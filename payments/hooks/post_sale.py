"""Post-sale hook implementations for payments."""

import logging

import pluggy

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
        """Call the implementation of this, so we can test it more easily."""
        from payments.api import process_post_sale_webhooks

        process_post_sale_webhooks(order_id, source)
