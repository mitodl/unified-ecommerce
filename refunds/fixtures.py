"""Test fixtures for refunds."""

import pytest

from payments.factories import OrderFactory, LineFactory
from payments.models import Order, Line
from refunds.factories import RequestFactory, RequestLineFactory
from system_meta.factories import ProductFactory

@pytest.fixture
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
