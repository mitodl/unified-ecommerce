"""Test fixtures for refunds."""

import faker
import pytest

from payments.factories import OrderFactory
from payments.models import Line, Order
from refunds.factories import (
    RequestRecipientFactory,
)
from system_meta.factories import IntegratedSystemFactory, ProductFactory

FAKE = faker.Faker()


@pytest.fixture()
def completed_order(user, integrated_system):
    """Create a completed order."""

    order = OrderFactory(
        purchaser=user,
        integrated_system=integrated_system,
        state=Order.STATE.FULFILLED,
    )

    products = ProductFactory.create_batch(3, system=integrated_system)

    for product in products:
        Line.from_product(product, order=order, quantity=1)

    order.refresh_from_db()

    return order


@pytest.fixture(autouse=True)
def refund_request_recipients():
    """
    Create refund request recipients and some integrated systems.

    Returns the system slugs with the recipients created.
    """

    systems = IntegratedSystemFactory.create_batch(3)
    return {
        system.slug: [
            RequestRecipientFactory.create(
                email=FAKE.unique.email(),
                integrated_system=system,
            )
            for _ in range(3)
        ]
        for system in systems
    }
