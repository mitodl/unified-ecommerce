"""Tests for post-sale hooks."""

import pytest
import reversion
from reversion.models import Version

from payments.constants import PAYMENT_HOOK_ACTION_POST_SALE
from payments.factories import LineFactory, OrderFactory
from payments.hooks.post_sale import IntegratedSystemWebhooks
from payments.models import Order
from payments.serializers.v0 import WebhookBase, WebhookBaseSerializer, WebhookOrder
from system_meta.factories import ProductFactory
from system_meta.models import IntegratedSystem
from unified_ecommerce.constants import (
    POST_SALE_SOURCE_BACKOFFICE,
    POST_SALE_SOURCE_REDIRECT,
)

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def fulfilled_order():
    """Create a fulfilled order."""

    order = OrderFactory.create(state=Order.STATE.FULFILLED)

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()
    LineFactory.create(order=order, product_version=product_version)

    return order


@pytest.mark.parametrize(
    "source", [POST_SALE_SOURCE_BACKOFFICE, POST_SALE_SOURCE_REDIRECT]
)
def test_integrated_system_webhook(mocker, fulfilled_order, source):
    """Test fire the webhook."""

    mocked_request = mocker.patch("requests.post")
    webhook = IntegratedSystemWebhooks()
    system_id = fulfilled_order.lines.first().product_version.field_dict["system_id"]
    system = IntegratedSystem.objects.get(pk=system_id)

    order_info = WebhookOrder(
        order=fulfilled_order,
        lines=fulfilled_order.lines.all(),
    )

    webhook_data = WebhookBase(
        type=PAYMENT_HOOK_ACTION_POST_SALE,
        system_key=system.api_key,
        user=fulfilled_order.purchaser,
        data=order_info,
    )

    serialized_webhook_data = WebhookBaseSerializer(webhook_data)

    webhook.post_sale_impl(fulfilled_order.id, source)

    mocked_request.assert_called_with(
        system.webhook_url, json=serialized_webhook_data.data, timeout=30
    )


@pytest.mark.parametrize(
    "source", [POST_SALE_SOURCE_BACKOFFICE, POST_SALE_SOURCE_REDIRECT]
)
def test_integrated_system_webhook_multisystem(mocker, fulfilled_order, source):
    """Test fire the webhook with an order with lines from >1 system."""

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()
    LineFactory.create(order=fulfilled_order, product_version=product_version)

    mocked_request = mocker.patch("requests.post")
    webhook = IntegratedSystemWebhooks()

    serialized_calls = []

    for system in IntegratedSystem.objects.all():
        order_info = WebhookOrder(
            order=fulfilled_order,
            lines=[
                line
                for line in fulfilled_order.lines.all()
                if line.product.system.slug == system.slug
            ],
        )

        webhook_data = WebhookBase(
            type=PAYMENT_HOOK_ACTION_POST_SALE,
            system_key=system.api_key,
            user=fulfilled_order.purchaser,
            data=order_info,
        )

        serialized_order = WebhookBaseSerializer(webhook_data).data
        serialized_calls.append(
            mocker.call(system.webhook_url, json=serialized_order, timeout=30)
        )

    webhook.post_sale_impl(fulfilled_order.id, source)

    assert mocked_request.call_count == 2
    mocked_request.assert_has_calls(serialized_calls, any_order=True)
