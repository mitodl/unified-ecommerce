"""Post-sale hook implementations for payments."""

import pluggy

from payments.tasks import successful_order_payment_email_task

hookimpl = pluggy.HookimplMarker("unified_ecommerce")


class PostSaleSendEmails:
    """Send email when the order is fulfilled."""

    @hookimpl
    def post_sale(self, order_id, source):  # noqa: ARG002
        """Send email when the order is fulfilled."""
        successful_order_payment_email_task.delay(
            order_id,
            "Successful Order Payment",
            "Your payment has been successfully processed.",
        )


class IntegratedSystemWebhooks:
    """Figures out what webhook endpoints to call, and calls them."""

    @hookimpl
    def post_sale(self, order_id, source):
        """Call the implementation of this, so we can test it more easily."""
        from payments.api import process_post_sale_webhooks

        process_post_sale_webhooks(order_id, source)
