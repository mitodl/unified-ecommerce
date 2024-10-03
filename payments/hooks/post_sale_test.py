"""Tests for post-sale hooks."""

import pytest
import reversion
from reversion.models import Version

from payments.factories import LineFactory, OrderFactory
from payments.models import Order
from system_meta.factories import ProductFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def pending_complete_order():
    """Create a pending order with line items."""

    order = OrderFactory.create(state=Order.STATE.PENDING)

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()
    LineFactory.create(order=order, product_version=product_version)

    return order


def test_post_sale_webhook_called(mocker, pending_complete_order):
    """Test that the post-sale webhooks get called."""

    mocked_webhook = mocker.patch("payments.api.process_post_sale_webhooks")

    mocked_transaction_data = {
        "transaction_id": "12345",
        "amount": 0,
    }

    pending_complete_order.fulfill(mocked_transaction_data)
    pending_complete_order.save()

    assert pending_complete_order.state == Order.STATE.FULFILLED
    mocked_webhook.assert_called()


def test_post_sale_webhook_not_called_when_no_url(mocker, pending_complete_order):
    """
    Test that the post-sale webhooks aren't called if there's not a URL to call.

    This checks to make sure the processor gets called, but *not* the dispatcher.
    """

    mocked_webhook = mocker.patch("payments.api.process_post_sale_webhooks")
    mocked_webhook_dispatcher = mocker.patch("payments.tasks.send_post_sale_webhook")

    mocked_transaction_data = {
        "transaction_id": "12345",
        "amount": 0,
    }

    products = [line.product for line in pending_complete_order.lines.all()]
    for product in products:
        product.system.webhook_url = ""
        product.system.save()

    pending_complete_order.refresh_from_db()

    pending_complete_order.fulfill(mocked_transaction_data)
    pending_complete_order.save()

    assert pending_complete_order.state == Order.STATE.FULFILLED
    mocked_webhook.assert_called()
    mocked_webhook_dispatcher.assert_not_called()
