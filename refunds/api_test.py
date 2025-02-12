"""Tests for refunds API functions."""
# ruff: noqa: F401, F811

import pytest
from mitol.payment_gateway.api import ProcessorResponse

from payments.factories import OrderFactory
from payments.models import Line, Order
from refunds.api import create_request_from_order
from refunds.factories import RequestRecipientFactory
from system_meta.factories import ProductFactory
from system_meta.fixtures import integrated_system
from unified_ecommerce.constants import REFUND_STATUS_APPROVED, REFUND_STATUS_DENIED

pytestmark = pytest.mark.django_db


def mock_refunds_hookimpls(mocker, exceptfor: str | None = None):
    """
    Mock the hook implementations for refunds, except for the one specified.

    There's a tuple in here to map the hookimpls to a shorter name. This needs to
    be updated when hookimpls are updated.

    Args:
    - mocker: The mocker fixture
    - exceptfor: The name of the step to skip
    Returns:
    - A dictionary of the mocked steps
    """

    hookimpls = [
        ("send_processing_codes", "refunds.hooks.refund_created.RefundCreatedHooks.send_processing_codes"),
        ("send_denial_email", "refunds.mail_api.send_refund_denied_email"),
        ("update_google_sheets", "refunds.sheets.update_google_sheets"),
    ]

    mocked = {}

    for (shortname, hookimpl) in hookimpls:
        if exceptfor is None or shortname != exceptfor:
            mocked[shortname] = mocker.patch(hookimpl)

    return mocked


def create_test_order(user, integrated_system, *, state=Order.STATE.FULFILLED, lines=3):
    """Create a test order."""

    order = OrderFactory(
        purchaser=user,
        integrated_system=integrated_system,
        state=state,
    )
    for _ in range(lines if lines else 3):
        Line.from_product(
            ProductFactory.create(system=integrated_system), order=order, quantity=1
        )

    return order


@pytest.mark.parametrize("state", Order.STATE.choices)
def test_create_request_from_order_invalid_state(user, integrated_system, state):
    """Make sure a refund can't be created unless the order is fulfilled."""

    state_const = state[0]
    order = create_test_order(user, integrated_system, state=state_const)

    if state_const != Order.STATE.FULFILLED:
        with pytest.raises(ValueError) as exc:  # noqa: PT011
            create_request_from_order(user, order)

        assert "Order must be fulfilled to create a refund request." in str(exc.value)
    else:
        assert create_request_from_order(user, order)


def test_create_request_from_order(user, integrated_system):
    """Test that a refund can be created from a completed order."""

    recipient = RequestRecipientFactory.create(integrated_system=integrated_system)
    completed_order = create_test_order(user, integrated_system)
    request = create_request_from_order(user, completed_order)

    assert request.order == completed_order

    order_lines = completed_order.lines.all()
    refund_lines = request.lines.all()

    assert len(refund_lines) == len(order_lines)

    for line in refund_lines:
        assert line in order_lines

    assert request.process_code.count() == 1
    assert request.process_code.first().email == recipient.email


def test_create_request_from_order_subset(user, integrated_system):
    """Test that the refund can be created with some lines from the order."""

    recipient = RequestRecipientFactory.create(integrated_system=integrated_system)
    order = create_test_order(user, integrated_system)

    order_lines = order.lines.all()
    refund_lines = order_lines[:2]
    Line.from_product(
        ProductFactory.create(system=integrated_system), order=order, quantity=1
    )

    request = create_request_from_order(user, order, lines=refund_lines)

    assert request.order == order

    assert len(request.lines.all()) == len(refund_lines)
    for line in refund_lines:
        assert line in request.lines.all()

    assert request.process_code.count() == 1
    assert request.process_code.first().email == recipient.email


def test_process_denied_refund(mocker, user, integrated_system):
    """Test that the refund can be denied."""

    completed_order = create_test_order(user, integrated_system)
    request = create_request_from_order(user, completed_order)

    mocked_hooks = mock_refunds_hookimpls(mocker)

    request.deny("Test reason")

    request.refresh_from_db()

    assert request.status == REFUND_STATUS_DENIED

    assert mocked_hooks["send_denial_email"].called
    assert mocked_hooks["update_google_sheets"].called
    assert not mocked_hooks["send_approval_email"].called

    for line in request.lines.all():
        assert line.status == REFUND_STATUS_DENIED


def test_process_approved_refund(mocker, user, integrated_system):
    """Test that the refund can be approved."""

    completed_order = create_test_order(user, integrated_system)
    request = create_request_from_order(user, completed_order)

    sample_response_data = {
        "id": "12345",  # it only has id in refund response, no transaction_id
        "refundAmountDetails": {"refundAmount": float(request.total_requested)},
    }
    sample_response = ProcessorResponse(
        state=ProcessorResponse.STATE_PENDING,
        response_data=sample_response_data,
        transaction_id="1234",
        message="",
        response_code="",
    )

    mocked_start_refund = mocker.patch("mitol.payment_gateway.api.PaymentGateway.start_refund", return_value=sample_response)
    mocked_hooks = mock_refunds_hookimpls(mocker)

    request.approve("Test reason")

    request.refresh_from_db()
    assert request.status == REFUND_STATUS_APPROVED

    assert not mocked_hooks["send_denial_email"].called
    assert mocked_hooks["send_approval_email"].called
    assert mocked_hooks["update_google_sheets"].called

    for line in request.lines.all():
        assert line.status == REFUND_STATUS_APPROVED
