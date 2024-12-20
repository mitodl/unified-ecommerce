"""Tests for Celery tasks in payments."""

import pytest

from payments.constants import PAYMENT_HOOK_ACTION_TEST
from payments.serializers.v0 import WebhookBase, WebhookBaseSerializer, WebhookTest
from payments.tasks import dispatch_webhook
from system_meta.factories import IntegratedSystemFactory

pytestmark = [pytest.mark.django_db]


def test_dispatch_webhook(mocker, user):
    """
    Test that the webhook dispatcher dispatches webhooks.

    This is a pretty generic dispatcher - we'll construct something simple and
    then dispatch it, and make sure the data we dispatched matches what we expect.
    """

    system = IntegratedSystemFactory.create()

    webhook_data = WebhookBaseSerializer(
        WebhookBase(
            system_slug=system.slug,
            system_key=system.api_key,
            user=user,
            type=PAYMENT_HOOK_ACTION_TEST,
            data=WebhookTest(
                some_data="some data",
            ),
        )
    ).data

    mocked_post = mocker.patch("requests.post")

    dispatch_webhook(
        system.webhook_url,
        webhook_data,
    )

    mocked_post.assert_called_with(
        system.webhook_url,
        json=webhook_data,
        timeout=30,
    )
