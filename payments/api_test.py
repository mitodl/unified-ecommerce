"""Tests for Ecommerce api"""

import random
import uuid

import pytest
import reversion
from CyberSource.rest import ApiException
from django.conf import settings
from django.urls import reverse
from factory import Faker, fuzzy
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse
from reversion.models import Version

from payments.api import (
    check_and_process_pending_orders_for_resolution,
    generate_checkout_payload,
    process_cybersource_payment_response,
    process_post_sale_webhooks,
    refund_order,
)
from payments.constants import PAYMENT_HOOK_ACTION_POST_SALE
from payments.exceptions import PaymentGatewayError, PaypalRefundError
from payments.factories import (
    LineFactory,
    OrderFactory,
    TransactionFactory,
)
from payments.models import (
    Basket,
    BasketItem,
    FulfilledOrder,
    Order,
    Transaction,
)
from payments.serializers.v0 import WebhookBase, WebhookBaseSerializer, WebhookOrder
from system_meta.factories import ProductFactory
from system_meta.models import IntegratedSystem
from unified_ecommerce.constants import (
    POST_SALE_SOURCE_BACKOFFICE,
    POST_SALE_SOURCE_REDIRECT,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
)
from unified_ecommerce.factories import UserFactory
from unified_ecommerce.test_utils import generate_mocked_request

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def fulfilled_order():
    """Fixture for creating a fulfilled order"""
    return OrderFactory.create(state=Order.STATE.FULFILLED)


@pytest.fixture()
def fulfilled_transaction(fulfilled_order):
    """Fixture to creating a fulfilled transaction"""
    payment_amount = 10.00
    fulfilled_sample = {
        "transaction_id": "1234",
        "req_amount": payment_amount,
        "req_currency": "USD",
    }

    return TransactionFactory.create(
        transaction_id="1234",
        transaction_type=TRANSACTION_TYPE_PAYMENT,
        data=fulfilled_sample,
        order=fulfilled_order,
    )


@pytest.fixture()
def fulfilled_paypal_transaction(fulfilled_order):
    """Fixture to creating a fulfilled transaction"""
    payment_amount = 10.00
    fulfilled_sample = {
        "transaction_id": "1234",
        "req_amount": payment_amount,
        "req_currency": "USD",
        "paypal_token": "EC-" + str(fuzzy.FuzzyText(length=17)),
        "paypal_payer_id": str(fuzzy.FuzzyText(length=13)),
        "paypal_fee_amount": payment_amount,
        "paypal_payer_status": "unverified",
        "paypal_address_status": "Confirmed",
        "paypal_customer_email": str(Faker("ascii_email")),
        "paypal_payment_status": "Completed",
        "paypal_pending_reason": "order",
    }

    return TransactionFactory.create(
        transaction_id="1234",
        transaction_type=TRANSACTION_TYPE_PAYMENT,
        data=fulfilled_sample,
        order=fulfilled_order,
    )


@pytest.fixture()
def fulfilled_complete_order():
    """Create a fulfilled order with line items."""

    order = OrderFactory.create(state=Order.STATE.FULFILLED)

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()
    LineFactory.create(
        order=order,
        product_version=product_version,
        discounted_price=product_version.field_dict["price"],
    )

    return order


@pytest.fixture()
def products():
    """Create products"""
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


@pytest.fixture()
def user(db):
    """Create a user"""
    return UserFactory.create()


@pytest.fixture(autouse=True)
def _payment_gateway_settings():
    """Mock payment gateway settings"""
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = "Test Security Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = "Test Access Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = uuid.uuid4()


def test_cybersource_refund_no_order():
    """Test that refund_order throws FulfilledOrder.DoesNotExist exception when the order doesn't exist"""

    with pytest.raises(FulfilledOrder.DoesNotExist):
        refund_order(order_id=1)  # Caling refund with random Id


def create_basket(user, products):
    """
    Bootstrap a basket with a product in it for testing the discount
    redemption APIs
    """
    integrated_system = products[0].system
    basket = Basket(user=user, integrated_system=integrated_system)
    basket.save()

    basket_item = BasketItem(
        product=products[random.randrange(0, len(products))],  # noqa: S311
        basket=basket,
        quantity=1,
    )
    basket_item.save()

    return basket


@pytest.mark.parametrize(
    "order_state",
    [
        Order.STATE.REFUNDED,
        Order.STATE.ERRORED,
        Order.STATE.PENDING,
        Order.STATE.DECLINED,
        Order.STATE.CANCELED,
        Order.STATE.REVIEW,
    ],
)
def test_cybersource_refund_no_fulfilled_order(order_state):
    """
    Test that refund_order returns logs properly and False when there is no
    Fulfilled order against the given order_id
    """

    unfulfilled_order = OrderFactory.create(state=order_state)
    refund_response, message = refund_order(order_id=unfulfilled_order.id)
    assert (
        f"Order with order_id {unfulfilled_order.id} is not in fulfilled state."
        in message
    )
    assert refund_response is False


def test_cybersource_refund_no_order_id():
    """
    Test that refund_order returns logs properly and False when there is no
    Fulfilled order against the given order_id
    """

    refund_response, message = refund_order()
    assert (
        "Either order_id or reference_number is required to fetch the Order." in message
    )
    assert refund_response is False


def test_cybersource_order_no_transaction(fulfilled_order):
    """
    Test that refund_order returns False when there is no transaction against a
    fulfilled order. Ideally, there should be a payment type transaction for a
    fulfilled order.
    """

    fulfilled_order = OrderFactory.create(state=Order.STATE.FULFILLED)
    refund_response, message = refund_order(order_id=fulfilled_order.id)
    assert (
        f"There is no associated transaction against order_id {fulfilled_order.id}"
        in message
    )
    assert refund_response is False


@pytest.mark.parametrize(
    ("order_state"),
    [
        (ProcessorResponse.STATE_PENDING),
        (ProcessorResponse.STATE_DUPLICATE),
    ],
)
def test_order_refund_success(mocker, order_state, fulfilled_transaction):
    """
    Test that appropriate data is created for a successful refund and its
    state changes to REFUNDED
    """

    sample_response_data = {
        "id": "12345",  # it only has id in refund response, no transaction_id
        "refundAmountDetails": {"refundAmount": float(fulfilled_transaction.amount)},
    }
    sample_response = ProcessorResponse(
        state=order_state,
        response_data=sample_response_data,
        transaction_id="1234",
        message="",
        response_code="",
    )

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        return_value=sample_response,
    )

    if order_state == ProcessorResponse.STATE_DUPLICATE:
        with pytest.raises((PaypalRefundError, PaymentGatewayError)):
            refund_success, _ = refund_order(
                order_id=fulfilled_transaction.order.id,
            )

        return
    else:
        refund_success, _ = refund_order(
            order_id=fulfilled_transaction.order.id,
        )

    # There should be two transaction objects (One for payment and other for refund)
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_PAYMENT,
        ).count()
        == 1
    )
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 1
    )
    assert refund_success is True

    # Refund transaction object should have appropriate data
    refund_transaction = Transaction.objects.filter(
        order=fulfilled_transaction.order.id, transaction_type=TRANSACTION_TYPE_REFUND
    ).first()

    assert refund_transaction.data == sample_response_data
    assert refund_transaction.amount == fulfilled_transaction.amount

    # The state of the order should be REFUNDED after a successful refund
    fulfilled_transaction.order.refresh_from_db()
    assert fulfilled_transaction.order.state == Order.STATE.REFUNDED


def test_order_refund_success_with_ref_num(mocker, fulfilled_transaction):
    """Test a successful refund based only on reference number"""
    sample_response_data = {
        "id": "12345",
        "refundAmountDetails": {"refundAmount": float(fulfilled_transaction.amount)},
    }
    sample_response = ProcessorResponse(
        state=ProcessorResponse.STATE_PENDING,
        response_data=sample_response_data,
        transaction_id="1234",
        message="",
        response_code="",
    )
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        return_value=sample_response,
    )
    refund_success, message = refund_order(
        reference_number=fulfilled_transaction.order.reference_number
    )
    # There should be two transaction objects (One for payment and other for refund)
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_PAYMENT,
        ).count()
        == 1
    )
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 1
    )
    assert refund_success is True
    assert message == ""

    # Refund transaction object should have appropriate data
    refund_transaction = Transaction.objects.filter(
        order=fulfilled_transaction.order.id, transaction_type=TRANSACTION_TYPE_REFUND
    ).first()

    assert refund_transaction.data == sample_response_data
    assert refund_transaction.amount == fulfilled_transaction.amount

    # The state of the order should be REFUNDED after a successful refund
    fulfilled_transaction.order.refresh_from_db()
    assert fulfilled_transaction.order.state == Order.STATE.REFUNDED


def test_order_refund_failure(mocker, fulfilled_transaction):
    """
    Test that refund operation returns False when there was a failure in
    refund
    """
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        side_effect=ApiException(),
    )

    def run_refund_order(order_id):
        refund_response, _ = refund_order(order_id=order_id)
        assert refund_response is False

    with pytest.raises(ApiException):
        run_refund_order(order_id=fulfilled_transaction.order.id)

    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 0
    )


def test_order_refund_failure_no_exception(mocker, fulfilled_transaction):
    """
    Test that refund operation throws an exception if the gateway returns
    an error state
    """

    class MockedGatewayResponse:
        state = (ProcessorResponse.STATE_ERROR,)
        message = ("This is an error message. Testing 123456",)

    error_return = MockedGatewayResponse()

    patched_refund_method = mocker.patch.object(PaymentGateway, "start_refund")
    patched_refund_method.return_value = error_return

    with pytest.raises((PaymentGatewayError, PaypalRefundError)) as exc:
        refund_order(order_id=fulfilled_transaction.order.id)

    assert "Testing 123456" in str(exc.value)

    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 0
    )


def test_paypal_refunds(fulfilled_paypal_transaction):
    """
    PayPal transactions should fail before they get to the payment gateway.
    """

    with pytest.raises((PaymentGatewayError, PaypalRefundError)) as exc:
        refund_order(order_id=fulfilled_paypal_transaction.order.id)

    assert "PayPal" in str(exc.value)


def test_process_cybersource_payment_response(rf, mocker, user, products):
    """
    Test that ensures the response from Cybersource for an ACCEPTed payment
    updates the orders state
    """
    mocker.patch("requests.post")
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=True,
    )
    create_basket(user, products)
    resp = generate_checkout_payload(generate_mocked_request(user), products[0].system)

    payload = resp["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": "ACCEPT",
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    request = rf.post(reverse("v0:checkout-result-callback"), payload)

    # This is checked on the BackofficeCallbackView and CheckoutCallbackView
    # POST endpoints since we expect to receive a response to both from
    # Cybersource.  If the current state is PENDING, then we should process
    # the response.
    assert order.state == Order.STATE.PENDING
    result = process_cybersource_payment_response(request, order)
    assert result == Order.STATE.FULFILLED


def test_process_cybersource_payment_decline_response(
    rf, mocker, user_client, user, products
):
    """
    Test that ensures the response from Cybersource for an DECLINEd payment
    updates the orders state
    """

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=True,
    )
    create_basket(user, products)

    resp = generate_checkout_payload(generate_mocked_request(user), products[0].system)

    payload = resp["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": "DECLINE",
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    request = rf.post(reverse("v0:checkout-result-callback"), payload)

    # This is checked on the BackofficeCallbackView and CheckoutCallbackView
    # POST endpoints since we expect to receive a response to both from
    # Cybersource.  If the current state is PENDING, then we should process
    # the response.
    assert order.state == Order.STATE.PENDING

    result = process_cybersource_payment_response(request, order)
    assert result == Order.STATE.DECLINED
    order.refresh_from_db()


@pytest.mark.parametrize("test_type", [None, "fail", "empty"])
def test_check_and_process_pending_orders_for_resolution(mocker, test_type):
    """
    Tests the pending order check. test_type can be:
    - None - there's an order and it was found
    - fail - there's an order but the payment failed (failed status in CyberSource)
    - empty - order isn't pending
    """
    order = OrderFactory.create(state=Order.STATE.PENDING)

    test_payload = {
        "utf8": "",
        "message": "Request was processed successfully.",
        "decision": "100",
        "auth_code": "888888",
        "auth_time": "2023-02-09T20:06:51Z",
        "signature": "",
        "req_amount": "999",
        "req_locale": "en-us",
        "auth_amount": "999",
        "reason_code": "100",
        "req_currency": "USD",
        "auth_avs_code": "X",
        "auth_response": "100",
        "req_card_type": "",
        "request_token": "",
        "card_type_name": "",
        "req_access_key": "",
        "req_item_0_sku": "60-2",
        "req_profile_id": "2BA30484-75E7-4C99-A7D4-8BD7ADE4552D",
        "transaction_id": "6759732112426719104003",
        "req_card_number": "",
        "req_consumer_id": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
        "req_item_0_code": "60",
        "req_item_0_name": "course-v1:edX+E2E-101+course",
        "signed_date_time": "2023-02-09T20:06:51Z",
        "auth_avs_code_raw": "I1",
        "auth_trans_ref_no": "123456789619999",
        "bill_trans_ref_no": "123456789619999",
        "req_bill_to_email": "testlearner@odl.local",
        "req_payment_method": "card",
        "signed_field_names": "",
        "req_bill_to_surname": "LEARNER",
        "req_item_0_quantity": 1,
        "req_line_item_count": 1,
        "req_bill_to_forename": "TEST",
        "req_card_expiry_date": "02-2025",
        "req_reference_number": f"{order.reference_number}",
        "req_transaction_type": "sale",
        "req_transaction_uuid": "",
        "req_item_0_tax_amount": "0",
        "req_item_0_unit_price": "999",
        "req_customer_ip_address": "172.19.0.8",
        "req_bill_to_address_city": "Tallahasseeeeeeee",
        "req_bill_to_address_line1": "555 123 Place",
        "req_bill_to_address_state": "FL",
        "req_merchant_defined_data1": "1",
        "req_bill_to_address_country": "US",
        "req_bill_to_address_postal_code": "81992",
        "req_override_custom_cancel_page": "https://rc.mitxonline.mit.edu/checkout/result/",
        "req_override_custom_receipt_page": "https://rc.mitxonline.mit.edu/checkout/result/",
        "req_card_type_selection_indicator": "001",
    }

    retval = {}

    if test_type == "fail":
        test_payload["reason_code"] = "999"

    if test_type == "empty":
        order.state = Order.STATE.CANCELED
        order.save()
        order.refresh_from_db()

    if test_type is None or test_type == "fail":
        retval = {f"{order.reference_number}": test_payload}

    mocked_gateway_func = mocker.patch(
        "mitol.payment_gateway.api.CyberSourcePaymentGateway.find_and_get_transactions",
        return_value=retval,
    )

    (fulfilled, cancelled, errored) = check_and_process_pending_orders_for_resolution()

    if test_type == "empty":
        assert not mocked_gateway_func.called
        assert (fulfilled, cancelled, errored) == (0, 0, 0)
    elif test_type == "fail":
        order.refresh_from_db()
        assert order.state == Order.STATE.CANCELED
        assert (fulfilled, cancelled, errored) == (0, 1, 0)
    else:
        order.refresh_from_db()
        assert order.state == Order.STATE.FULFILLED
        assert (fulfilled, cancelled, errored) == (1, 0, 0)


@pytest.mark.parametrize(
    "source", [POST_SALE_SOURCE_BACKOFFICE, POST_SALE_SOURCE_REDIRECT]
)
def test_integrated_system_webhook(mocker, fulfilled_complete_order, source):
    """Test fire the webhook."""

    mocked_request = mocker.patch("requests.post")
    system_id = fulfilled_complete_order.lines.first().product_version.field_dict[
        "system_id"
    ]
    system = IntegratedSystem.objects.get(pk=system_id)

    order_info = WebhookOrder(
        order=fulfilled_complete_order,
        lines=fulfilled_complete_order.lines.all(),
    )

    webhook_data = WebhookBase(
        type=PAYMENT_HOOK_ACTION_POST_SALE,
        system_key=system.api_key,
        user=fulfilled_complete_order.purchaser,
        data=order_info,
    )

    serialized_webhook_data = WebhookBaseSerializer(webhook_data)

    process_post_sale_webhooks(fulfilled_complete_order.id, source)

    mocked_request.assert_called_with(
        system.webhook_url, json=serialized_webhook_data.data, timeout=30
    )


@pytest.mark.parametrize(
    "source", [POST_SALE_SOURCE_BACKOFFICE, POST_SALE_SOURCE_REDIRECT]
)
def test_integrated_system_webhook_multisystem(
    mocker, fulfilled_complete_order, source
):
    """Test fire the webhook with an order with lines from >1 system."""

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()
    LineFactory.create(order=fulfilled_complete_order, product_version=product_version, discounted_price=product_version.field_dict["price"])

    mocked_request = mocker.patch("requests.post")

    serialized_calls = []

    for system in IntegratedSystem.objects.all():
        order_info = WebhookOrder(
            order=fulfilled_complete_order,
            lines=[
                line
                for line in fulfilled_complete_order.lines.all()
                if line.product.system.slug == system.slug
            ],
        )

        webhook_data = WebhookBase(
            type=PAYMENT_HOOK_ACTION_POST_SALE,
            system_key=system.api_key,
            user=fulfilled_complete_order.purchaser,
            data=order_info,
        )

        serialized_order = WebhookBaseSerializer(webhook_data).data
        serialized_calls.append(
            mocker.call(system.webhook_url, json=serialized_order, timeout=30)
        )

    process_post_sale_webhooks(fulfilled_complete_order.id, source)

    assert mocked_request.call_count == 2
    mocked_request.assert_has_calls(serialized_calls, any_order=True)
