"""Post-sale hook implementations for payments."""

import logging

import pluggy

hookimpl = pluggy.HookimplMarker("unified_ecommerce")


class TestPostSale:
    """Test the post-sale hook."""

    @hookimpl
    def post_sale(self, order_id, source):
        """Implement a basic post-sale hook."""
        log = logging.getLogger(__name__)

        msg = f"Received post-sale event for order {order_id} with source {source}"
        log.error(msg)


class PostSaleSendEmails:
    """Send email when the order is fulfilled."""

    @hookimpl
    def post_sale(self, order_id, source):
        """Send email when the order is fulfilled."""
        log = logging.getLogger(__name__)

        msg = f"Sending email for order {order_id} with source {source}"
        log.error(msg)
