"""Tests for refunds API functions."""

import pytest

from payments.models import Line, Order
from payments.factories import OrderFactory
from refunds.api import create_request_from_order
from refunds.fixtures import completed_order
from system_meta.factories import ProductFactory
from system_meta.fixtures import integrated_system


pytestmark = pytest.mark.django_db


def create_test_order(user, integrated_system, *, state=Order.STATE.FULFILLED, lines=3):
    """Create a test order."""

    order = OrderFactory(
        purchaser=user,
        integrated_system=integrated_system,
        state=state,
    )
    for _ in range(lines if lines else 3):
        Line.from_product(ProductFactory.create(system=integrated_system), order=order, quantity=1)

    return order


@pytest.mark.parametrize("state", Order.STATE.choices)
def test_create_request_from_order_invalid_state(user, integrated_system, state):
    """Make sure a refund can't be created unless the order is fulfilled."""

    state_const = state[0]
    order = create_test_order(user, integrated_system, state=state_const)

    if state_const != Order.STATE.FULFILLED:
        with pytest.raises(ValueError) as exc:
            create_request_from_order(user, order)

        assert "Order must be fulfilled to create a refund request." in str(exc.value)
    else:
        assert create_request_from_order(user, order)


def test_create_request_from_order(user, completed_order):
    """Test that a refund can be created from a completed order."""

    request = create_request_from_order(user, completed_order)

    assert request.order == completed_order

    order_lines = completed_order.lines.all()
    refund_lines = request.lines.all()

    assert len(refund_lines) == len(order_lines)

    for line in refund_lines:
        assert line in order_lines


def test_create_request_from_order_subset(user, integrated_system):
    """Test that the refund can be created with some lines from the order."""

    order = create_test_order(user, integrated_system)

    order_lines = order.lines.all()
    refund_lines = order_lines[:2]
    Line.from_product(ProductFactory.create(system=integrated_system), order=order, quantity=1)

    request = create_request_from_order(user, order, lines=refund_lines)

    assert request.order == order

    assert len(request.lines.all()) == len(refund_lines)
    for line in refund_lines:
        assert line in request.lines.all()
