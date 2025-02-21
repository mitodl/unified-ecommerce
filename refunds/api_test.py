"""Tests for refunds API functions."""
# ruff: noqa: F401, F811

from decimal import Decimal

import pytest
import reversion
from mitol.payment_gateway.api import ProcessorResponse

from payments.factories import (
    OrderFactory,
    PaymentTransactionFactory,
    PaypalPaymentTransactionFactory,
)
from payments.models import Line, Order
from refunds.api import create_request_from_order, process_approved_refund
from refunds.exceptions import RefundOrderPaymentTypeUnsupportedError
from refunds.factories import RequestRecipientFactory
from system_meta.factories import ProductFactory
from system_meta.fixtures import integrated_system
from unified_ecommerce.constants import (
    REFUND_STATUS_APPROVED,
    REFUND_STATUS_APPROVED_COMPLETE,
    REFUND_STATUS_DENIED,
)

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
        ("send_processing_codes", "refunds.api.create_request_access_codes"),
        ("send_denied_email", "refunds.mail_api.send_refund_denied_email"),
        ("send_issued_email", "refunds.mail_api.send_refund_issued_email"),
        ("update_google_sheets", "refunds.sheets.update_google_sheets"),
    ]

    mocked = {}

    for shortname, hookimpl in hookimpls:
        if exceptfor is None or shortname != exceptfor:
            mocked[shortname] = mocker.patch(hookimpl)

    return mocked


def create_test_order(
    user,
    integrated_system,
    *,
    state=Order.STATE.FULFILLED,
    lines=3,
    is_paypal=False,
    zero_value=False,
):
    """
    Create a test order.
    """

    order = OrderFactory(
        purchaser=user,
        integrated_system=integrated_system,
        state=state,
        total_price_paid=Decimal(0 if zero_value else 10.00),
    )
    for _ in range(lines if lines else 3):
        with reversion.create_revision():
            product = ProductFactory.create(
                system=integrated_system,
                price=0 if zero_value else 10.00,
            )
            product.save()

        line = Line.from_product(
            product=product,
            order=order,
            quantity=1,
            discounted_price=0 if zero_value else product.price,
        )
        line.save()

    order.refresh_from_db()

    if is_paypal:
        order.transactions.add(PaypalPaymentTransactionFactory.create(order=order))
    else:
        order.transactions.add(PaymentTransactionFactory.create(order=order))

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
        assert completed_order.lines.filter(pk=line.line.pk).exists()

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
        assert request.lines.filter(line__pk=line.pk).exists()

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

    assert mocked_hooks["send_denied_email"].called
    assert mocked_hooks["update_google_sheets"].called
    assert not mocked_hooks["send_issued_email"].called

    for line in request.lines.all():
        assert line.status == REFUND_STATUS_DENIED


@pytest.mark.parametrize("is_paypal", [True, False])
def test_process_approved_refund(mocker, user, integrated_system, is_paypal):
    """Test that the refund can be approved."""

    completed_order = create_test_order(
        user, integrated_system, is_paypal=is_paypal, lines=3
    )
    request = create_request_from_order(user, completed_order)

    assert request.lines.count() == 3

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

    mocked_start_refund = mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        return_value=sample_response,
    )
    mocked_hooks = mock_refunds_hookimpls(mocker)
    mocked_queue_call = mocker.patch(
        "refunds.tasks.queue_process_approved_refund.delay"
    )

    request.approve("Test reason")

    request.refresh_from_db()
    assert request.status == REFUND_STATUS_APPROVED

    assert mocked_queue_call.called

    # This would normally be called by the task we mocked up above.
    # Since that's mocked, we have to call it manually.

    if is_paypal:
        with pytest.raises(RefundOrderPaymentTypeUnsupportedError):
            process_approved_refund(request)

        # Make sure nothing changes.
        request.refresh_from_db()
        assert request.status == REFUND_STATUS_APPROVED
        for line in request.lines.all():
            assert line.status == REFUND_STATUS_APPROVED

        return

    process_approved_refund(request)

    assert not mocked_hooks["send_denied_email"].called
    assert mocked_hooks["send_issued_email"].called
    assert mocked_hooks["update_google_sheets"].called

    for line in request.lines.all():
        assert line.status == REFUND_STATUS_APPROVED_COMPLETE

    assert mocked_start_refund.called


def test_refund_zero_value_order(mocker, user, integrated_system):
    """
    Test refunding an order with zero value.

    Orders like this should complete on their own, without sending code batches
    or contacting CyberSource.
    """

    mocked_hooks = mock_refunds_hookimpls(mocker)
    mocked_queue_call = mocker.patch(
        "refunds.tasks.queue_process_approved_refund.delay"
    )
    mocked_start_refund = mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund"
    )

    completed_order = create_test_order(user, integrated_system, zero_value=True)

    assert completed_order.total_price_paid == Decimal(0)

    request = create_request_from_order(user, completed_order)

    assert mocked_queue_call.called
    assert request.status == REFUND_STATUS_APPROVED_COMPLETE

    process_approved_refund(request, auto_approved=True)

    assert not mocked_start_refund.called
    assert not mocked_hooks["send_processing_codes"].called
    assert not mocked_hooks["send_denied_email"].called
    assert mocked_hooks["send_issued_email"].called
    assert mocked_hooks["update_google_sheets"].called
