"""Tests for Ecommerce api"""

import random
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import reversion
from CyberSource.rest import ApiException
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest
from django.urls import reverse
from factory import Faker, fuzzy
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse
from reversion.models import Version

from payments.api import (
    check_blocked_countries,
    check_taxable,
    generate_checkout_payload,
    generate_discount_code,
    get_auto_apply_discounts_for_basket,
    get_redemption_type,
    get_users,
    locate_customer_for_basket,
    process_cybersource_payment_response,
    process_post_sale_webhooks,
    refund_order,
    send_post_sale_webhook,
    send_pre_sale_webhook,
    update_discount_codes,
)
from payments.constants import (
    PAYMENT_HOOK_ACTION_POST_SALE,
    PAYMENT_HOOK_ACTION_PRE_SALE,
)
from payments.dataclasses import CustomerLocationMetadata
from payments.exceptions import (
    PaymentGatewayError,
    PaypalRefundError,
    ProductBlockedError,
)
from payments.factories import (
    BasketFactory,
    BasketItemFactory,
    BlockedCountryFactory,
    BulkDiscountCollectionFactory,
    CompanyFactory,
    DiscountFactory,
    LineFactory,
    OrderFactory,
    RedeemedDiscountFactory,
    TaxRateFactory,
    TransactionFactory,
)
from payments.models import (
    Basket,
    BasketItem,
    Discount,
    FulfilledOrder,
    Order,
    Transaction,
)
from payments.serializers.v0 import (
    WebhookBase,
    WebhookBaseSerializer,
    WebhookBasket,
    WebhookBasketAction,
    WebhookOrder,
)
from system_meta.factories import IntegratedSystemFactory, ProductFactory
from system_meta.models import IntegratedSystem
from unified_ecommerce.constants import (
    ALL_DISCOUNT_TYPES,
    ALL_PAYMENT_TYPES,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_PERCENT_OFF,
    POST_SALE_SOURCE_BACKOFFICE,
    POST_SALE_SOURCE_REDIRECT,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
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
    """Test that refund_order throws FulfilledOrder.DoesNotExist exception when the order doesn"t exist"""

    with pytest.raises(FulfilledOrder.DoesNotExist):
        refund_order(order_id=1)  # Calling refund with random Id


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


@pytest.mark.parametrize(
    "source", [POST_SALE_SOURCE_BACKOFFICE, POST_SALE_SOURCE_REDIRECT]
)
def test_post_sale_webhook(mocker, fulfilled_complete_order, source):
    """Test fire the post-sale webhook."""

    mocked_task = mocker.patch("payments.tasks.dispatch_webhook.delay")
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
        system_slug=system.slug,
        system_key=system.api_key,
        user=fulfilled_complete_order.purchaser,
        data=order_info,
    )

    serialized_webhook_data = WebhookBaseSerializer(webhook_data)

    process_post_sale_webhooks(fulfilled_complete_order.id, source)

    mocked_task.assert_called_with(system.webhook_url, serialized_webhook_data.data)


def test_pre_sale_webhook(mocker, user, products):
    """Test that the pre-sale webhook triggers with the right data."""

    mocked_task = mocker.patch("payments.tasks.dispatch_webhook.delay")

    basket = BasketItemFactory.create(product=products[0], basket__user=user).basket
    system = basket.integrated_system

    order_info = WebhookBasket(
        product=products[0],
        action=WebhookBasketAction.ADD,
    )

    webhook_data = WebhookBase(
        type=PAYMENT_HOOK_ACTION_PRE_SALE,
        system_slug=system.slug,
        system_key=system.api_key,
        user=user,
        data=order_info,
    )

    serialized_webhook_data = WebhookBaseSerializer(webhook_data)

    send_pre_sale_webhook(basket, products[0], WebhookBasketAction.ADD)

    mocked_task.assert_called_with(system.webhook_url, serialized_webhook_data.data)


@pytest.mark.parametrize(
    "source", [POST_SALE_SOURCE_BACKOFFICE, POST_SALE_SOURCE_REDIRECT]
)
def test_post_sale_webhook_multisystem(mocker, fulfilled_complete_order, source):
    """Test fire the post-sale webhook with an order with lines from >1 system."""

    # Create an integrated system out of band to make sure this is actually
    # getting called correctly.
    _ = IntegratedSystemFactory.create()

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()
    LineFactory.create(
        order=fulfilled_complete_order,
        product_version=product_version,
        discounted_price=product_version.field_dict["price"],
    )

    mocked_task = mocker.patch("payments.tasks.dispatch_webhook.delay")

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

        if len(order_info.lines) == 0:
            continue

        webhook_data = WebhookBase(
            type=PAYMENT_HOOK_ACTION_POST_SALE,
            system_slug=system.slug,
            system_key=system.api_key,
            user=fulfilled_complete_order.purchaser,
            data=order_info,
        )

        serialized_order = WebhookBaseSerializer(webhook_data).data
        serialized_calls.append(mocker.call(system.webhook_url, serialized_order))

    process_post_sale_webhooks(fulfilled_complete_order.id, source)

    assert mocked_task.call_count == 2
    mocked_task.assert_has_calls(serialized_calls, any_order=True)


def test_get_auto_apply_discount_for_basket_auto_discount_exists_for_integrated_system():
    """
    Test that get_auto_apply_discount_for_basket returns the auto discount
    when it exists for the basket's integrated system.
    """
    basket = BasketFactory.create()
    auto_discount = Discount.objects.create(
        automatic=True,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        integrated_system=basket.integrated_system,
    )

    discount = get_auto_apply_discounts_for_basket(basket.id)
    assert discount[0] == auto_discount


def test_get_auto_apply_discount_for_basket_auto_discount_exists_for_product():
    """
    Test that get_auto_apply_discount_for_basket returns the auto discount
    when it exists for the basket's - basket item - product.
    """
    basket_item = BasketItemFactory.create()
    auto_discount = Discount.objects.create(
        automatic=True,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        product=basket_item.product,
    )

    discount = get_auto_apply_discounts_for_basket(basket_item.basket.id)
    assert discount[0] == auto_discount


def test_get_auto_apply_discount_for_basket_auto_discount_exists_for_user():
    """
    Test that get_auto_apply_discount_for_basket returns the auto discount
    when it exists for the basket's user.
    """
    basket = BasketFactory.create()
    auto_discount = Discount.objects.create(
        automatic=True,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
    )
    basket.user.discounts.add(auto_discount)
    discount = get_auto_apply_discounts_for_basket(basket.id)
    assert discount[0] == auto_discount


def test_get_auto_apply_discount_for_basket_multiple_auto_discount_exists_for_user_product_system():
    """
    Test that get_auto_apply_discount_for_basket returns multiple auto discount
    when they exist for the basket's - basket item - product, basket's user, and basket's integrated system.
    """
    basket_item = BasketItemFactory.create()
    user_discount = DiscountFactory.create(
        automatic=True,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        discount_code=uuid.uuid4(),
    )
    basket_item.basket.user.discounts.add(user_discount)
    DiscountFactory.create(
        automatic=True,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        integrated_system=basket_item.basket.integrated_system,
        discount_code=uuid.uuid4(),
    )
    DiscountFactory.create(
        automatic=True,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        product=basket_item.product,
        discount_code=uuid.uuid4(),
    )

    discount = get_auto_apply_discounts_for_basket(basket_item.basket.id)
    assert discount.count() == 3


def test_get_auto_apply_discount_for_basket_no_auto_discount_exists():
    """
    Test that get_auto_apply_discount_for_basket returns the no discount
    when no auto discount exists for the basket.
    """
    basket_item = BasketItemFactory.create()
    user_discount = DiscountFactory.create(
        automatic=False,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        discount_code=uuid.uuid4(),
    )
    basket_item.basket.user.discounts.add(user_discount)
    DiscountFactory.create(
        automatic=False,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        integrated_system=basket_item.basket.integrated_system,
        discount_code=uuid.uuid4(),
    )
    DiscountFactory.create(
        automatic=False,
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        product=basket_item.product,
        discount_code=uuid.uuid4(),
    )

    discount = get_auto_apply_discounts_for_basket(basket_item.basket.id)
    assert discount.count() == 0


@pytest.mark.parametrize("source", ["backoffice", "redirect"])
def test_send_post_sale_webhook_success(mocker, source):
    """Test sending the post-sale webhook successfully."""

    # Mock Order
    order = OrderFactory(reference_number="ORDER123")

    order_user = order.purchaser

    # Mock IntegratedSystem
    system = IntegratedSystemFactory(
        webhook_url="https://example.com/webhook",
        slug="system_slug",
        api_key="test_api_key",
    )

    # Mock dispatch_webhook.delay
    mocked_task = mocker.patch("payments.tasks.dispatch_webhook.delay")

    # Mock logger
    mock_logger = mocker.patch("payments.api.log")

    # Execute
    send_post_sale_webhook(system.id, order.id, source)

    # Assert
    mock_logger.info.assert_called_once_with(
        "send_post_sale_webhook: Calling webhook endpoint %s for order %s with source %s",
        "https://example.com/webhook",
        "ORDER123",
        source,
    )
    mocked_task.assert_called_once_with(
        "https://example.com/webhook",
        {
            "system_key": "test_api_key",
            "type": "postsale",
            "user": {
                "id": order_user.id,
                "global_id": order_user.global_id,
                "username": order_user.username,
                "email": order_user.email,
                "first_name": order_user.first_name,
                "last_name": order_user.last_name,
                "name": "",
            },
            "data": {
                "reference_number": "ORDER123",
                "total_price_paid": "10.00",
                "state": order.state,
                "lines": [],
                "refunds": [],
                "order": order.id,
            },
            "system_slug": "system_slug",
        },
    )


@pytest.mark.parametrize("source", ["backoffice", "redirect"])
def test_send_post_sale_webhook_order_not_found(source):
    """Test sending the post-sale webhook when the order does not exist."""

    # Mock Order to raise ObjectDoesNotExist
    order = OrderFactory(reference_number="ORDER123")

    # Mock IntegratedSystem
    system = IntegratedSystemFactory()

    # Execute and Assert
    with pytest.raises(ObjectDoesNotExist):
        send_post_sale_webhook(
            system.id, order.id + 1, source
        )  # Use a non-existent order ID


@pytest.mark.parametrize("source", ["backoffice", "redirect"])
def test_send_post_sale_webhook_system_not_found(source):
    """Test sending the post-sale webhook when the system does not exist."""

    # Mock Order
    order = OrderFactory(reference_number="ORDER123")

    # Execute and Assert
    with pytest.raises(ObjectDoesNotExist):
        send_post_sale_webhook(999, order.id, source)  # Use a non-existent system ID


def test_generate_discount_code_single():
    """
    Test generating a single discount code
    """
    # Setup
    test_user = UserFactory()
    company = CompanyFactory()
    product = ProductFactory()
    integrated_system = IntegratedSystemFactory()

    # Test
    codes = generate_discount_code(
        discount_type=DISCOUNT_TYPE_PERCENT_OFF,
        payment_type="credit_card",
        amount=Decimal("20.00"),
        codes="ABC123",
        count=1,
        users=[test_user.id],
        company=company.id,
        product=product.id,
        integrated_system=integrated_system.slug,
        activates="2023-01-01",
        expires="2023-12-31",
    )

    # Assert
    assert len(codes) == 1
    code = codes[0]
    assert code.discount_type == DISCOUNT_TYPE_PERCENT_OFF
    assert code.payment_type == "credit_card"
    assert code.amount == Decimal("20.00")
    assert code.discount_code == "ABC123"
    assert code.expiration_date == datetime(2023, 12, 31, 0, 0, tzinfo=UTC)
    assert code.activation_date == datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    assert code.company == company
    assert code.product == product
    assert code.integrated_system == integrated_system


def test_generate_discount_code_batch():
    """
    Test generating a batch of discount codes
    """
    # Setup
    prefix = "BATCH"

    # Test
    codes = generate_discount_code(
        discount_type=DISCOUNT_TYPE_PERCENT_OFF,
        payment_type="credit_card",
        amount=Decimal("10.00"),
        count=5,
        prefix=prefix,
    )

    # Assert
    assert len(codes) == 5
    for code in codes:
        assert code.discount_type == DISCOUNT_TYPE_PERCENT_OFF
        assert code.payment_type == "credit_card"
        assert code.amount == Decimal("10.00")
        assert code.discount_code.startswith(prefix)


def test_generate_discount_code_invalid_discount_type():
    """
    Test generating a discount code with an invalid discount type
    """
    with pytest.raises(ValueError, match="Invalid discount type") as excinfo:
        generate_discount_code(
            discount_type="invalid_type",
            payment_type="credit_card",
            amount=Decimal("10.00"),
        )
    assert "Invalid discount type" in str(excinfo.value)


def test_generate_discount_code_invalid_payment_type():
    """
    Test generating a discount code with an invalid payment type
    """
    with pytest.raises(
        ValueError, match="Payment type invalid_type is not valid"
    ) as excinfo:
        generate_discount_code(
            discount_type=DISCOUNT_TYPE_PERCENT_OFF,
            payment_type="invalid_type",
            amount=Decimal("10.00"),
        )
    assert "Payment type invalid_type is not valid" in str(excinfo.value)


def test_generate_discount_code_invalid_percent_amount():
    """
    Test generating a discount code with an invalid percent amount
    """
    with pytest.raises(
        ValueError,
        match="Discount amount 150.00 not valid for discount type percent-off",
    ) as excinfo:
        generate_discount_code(
            discount_type=DISCOUNT_TYPE_PERCENT_OFF,
            payment_type="credit_card",
            amount=Decimal("150.00"),
        )
    assert "Discount amount 150.00 not valid for discount type percent-off" in str(
        excinfo.value
    )


def test_generate_discount_code_missing_prefix_for_batch():
    """
    Test generating a batch of discount codes without a prefix
    """
    with pytest.raises(ValueError) as excinfo:  # noqa: PT011
        generate_discount_code(
            discount_type=DISCOUNT_TYPE_PERCENT_OFF,
            payment_type="credit_card",
            amount=Decimal("10.00"),
            count=2,
        )
    assert "You must specify a prefix to create a batch of codes" in str(excinfo.value)


def test_generate_discount_code_prefix_too_long():
    """
    Test generating a discount code with a prefix that is too long
    """
    with pytest.raises(ValueError) as excinfo:  # noqa: PT011
        generate_discount_code(
            discount_type=DISCOUNT_TYPE_PERCENT_OFF,
            payment_type="credit_card",
            amount=Decimal("10.00"),
            count=2,
            prefix="a" * 64,
        )
    assert (
        "Prefix aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa is 64 - prefixes must be 63 characters or less"
        in str(excinfo.value)
    )


def test_update_discount_codes_with_valid_discount_type():
    """
    Test updating discount codes with a valid discount type
    """
    discount = DiscountFactory()
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], discount_type=ALL_DISCOUNT_TYPES[0]
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.discount_type == ALL_DISCOUNT_TYPES[0]


def test_update_discount_codes_with_invalid_discount_type():
    """
    Test updating discount codes with an invalid discount type
    """
    discount = DiscountFactory()
    with pytest.raises(ValueError, match="Invalid discount type") as excinfo:
        update_discount_codes(
            discount_codes=[discount.discount_code], discount_type="INVALID_TYPE"
        )
    assert "Invalid discount type: INVALID_TYPE." in str(excinfo.value)


def test_update_discount_codes_with_valid_payment_type():
    """
    Test updating discount codes with a valid payment type
    """
    discount = DiscountFactory()
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], payment_type=ALL_PAYMENT_TYPES[0]
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.payment_type == ALL_PAYMENT_TYPES[0]


def test_update_discount_codes_with_invalid_payment_type():
    """
    Test updating discount codes with an invalid payment type
    """
    discount = DiscountFactory()
    with pytest.raises(
        ValueError, match="Payment type INVALID_TYPE is not valid."
    ) as excinfo:
        update_discount_codes(
            discount_codes=[discount.discount_code], payment_type="INVALID_TYPE"
        )
    assert "Payment type INVALID_TYPE is not valid." in str(excinfo.value)


def test_update_discount_codes_with_amount():
    """
    Test updating discount codes with an amount
    """
    discount = DiscountFactory()
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], amount="20.00"
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.amount == Decimal("20.00")


def test_update_discount_codes_with_activates_and_expires():
    """
    Test updating discount codes with activation and expiration dates
    """
    discount = DiscountFactory()
    activates = "2023-01-01"
    expires = "2023-12-31"
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], activates=activates, expires=expires
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.activation_date == datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    assert discount.expiration_date == datetime(2023, 12, 31, 0, 0, tzinfo=UTC)


def test_update_discount_codes_with_integrated_system():
    """
    Test updating discount codes with an integrated system
    """
    discount = DiscountFactory()
    integrated_system = IntegratedSystemFactory()
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code],
        integrated_system=integrated_system.slug,
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.integrated_system == integrated_system


def test_update_discount_codes_with_product():
    """
    Test updating discount codes with a product
    """
    discount = DiscountFactory()
    product = ProductFactory()
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], product=product.id
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.product == product


def test_update_discount_codes_with_users():
    """
    Test updating discount codes with users
    """
    discount = DiscountFactory()
    users = UserFactory.create_batch(3)
    user_emails = [user.email for user in users]
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], users=user_emails
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert set(discount.assigned_users.all()) == set(users)


def test_update_discount_codes_with_clear_users():
    """
    Test updating discount codes by clearing the assigned users
    """
    discount = DiscountFactory()
    users = UserFactory.create_batch(2)
    discount.assigned_users.set(users)
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], clear_users=True
    )
    assert updated_count == 1
    discount.refresh_from_db()
    assert discount.assigned_users.count() == 0


def test_update_discount_codes_with_prefix():
    """
    Test updating discount codes with a prefix
    """
    bulk_collection = BulkDiscountCollectionFactory()
    discounts = []
    discounts.append(
        DiscountFactory(
            discount_code="ABC1",
            bulk_discount_collection=bulk_collection,
            amount="10.00",
        )
    )
    discounts.append(
        DiscountFactory(
            discount_code="ABC2",
            bulk_discount_collection=bulk_collection,
            amount="10.00",
        )
    )
    discounts.append(
        DiscountFactory(
            discount_code="ABC3",
            bulk_discount_collection=bulk_collection,
            amount="10.00",
        )
    )
    updated_count = update_discount_codes(prefix=bulk_collection.prefix, amount="15.00")
    assert updated_count == 3
    for discount in discounts:
        discount.refresh_from_db()
        assert discount.amount == Decimal("15.00")


def test_update_discount_codes_exclude_redeemed_discounts():
    """
    Test updating discount codes with a prefix
    """
    discount = DiscountFactory(redemption_type=REDEMPTION_TYPE_ONE_TIME)
    RedeemedDiscountFactory(discount=discount)
    updated_count = update_discount_codes(
        discount_codes=[discount.discount_code], amount="10.00"
    )
    assert updated_count == 0
    discount.refresh_from_db()
    assert discount.amount != Decimal("10.00")


def test_locate_customer_for_basket_sets_customer_location(mocker):
    """
    Test that locate_customer_for_basket sets the customer location
    """
    test_user = UserFactory()
    product = ProductFactory()
    basket = BasketFactory(user=test_user)
    request = HttpRequest()
    request.user = test_user
    # Mock dependencies
    mock_determine_user_location = mocker.patch(
        "payments.api.determine_user_location",
        side_effect=["BlockedCountryLocation", "TaxCountryLocation"],
    )
    mock_get_flagged_countries = mocker.patch(
        "payments.api.get_flagged_countries",
        side_effect=[{"BlockedCountry"}, {"TaxCountry"}],
    )
    mock_get_client_ip = mocker.patch(
        "payments.api.get_client_ip",
        return_value="127.0.0.1",
    )
    mock_basket_save = mocker.patch.object(basket, "save")
    mock_basket_set_customer_location = mocker.patch.object(
        basket, "set_customer_location"
    )

    # Call the function
    locate_customer_for_basket(request, basket, product)

    # Assertions
    mock_get_client_ip.assert_called_once_with(request)
    mock_get_flagged_countries.assert_any_call("tax")
    mock_determine_user_location.assert_any_call(
        request,
        {"BlockedCountry"},
    )
    mock_determine_user_location.assert_any_call(
        request,
        {"TaxCountry"},
    )
    test = CustomerLocationMetadata(
        location_block="BlockedCountryLocation", location_tax="TaxCountryLocation"
    )
    mock_basket_set_customer_location.assert_any_call(test)
    mock_basket_save.assert_called_once()


def test_locate_customer_for_basket_logs_debug_info(mocker, caplog):
    """
    Test that locate_customer_for_basket logs debug information
    """
    test_user = UserFactory()
    product = ProductFactory()
    basket = BasketFactory(user=test_user)
    request = HttpRequest()
    request.user = test_user
    # Mock dependencies
    mocker.patch("payments.api.determine_user_location", return_value="SomeLocation")
    mocker.patch("payments.api.get_flagged_countries", return_value=set())
    mocker.patch("payments.api.get_client_ip", return_value="127.0.0.1")
    mocker.patch.object(basket, "save")
    mocker.patch.object(basket, "set_customer_location")

    # Call the function
    with caplog.at_level("DEBUG"):
        locate_customer_for_basket(request, basket, product)

    # Assert logs
    assert "locate_customer_for_basket: running for" in caplog.text
    assert str(request.user) in caplog.text
    assert "127.0.0.1" in caplog.text


def test_check_blocked_countries_blocked_for_country():
    """
    Test that ProductBlockedError is raised when the product is blocked for the user's country.
    """
    # Create test data
    test_user = UserFactory()
    test_user.profile.country_code = "US"
    test_user.save()
    product = ProductFactory()
    basket = BasketFactory(user=test_user, user_blockable_country_code="US")

    # Block the product for the user's country
    BlockedCountryFactory(country_code="US", product=product)

    # Call the function and expect an exception
    with pytest.raises(ProductBlockedError) as exc_info:
        check_blocked_countries(basket, product)

    # Verify the error message
    assert str(exc_info.value) == f"Product {product} blocked in country US"


def test_check_blocked_countries_not_blocked_for_other_country():
    """
    Test that no exception is raised when the product is blocked for another country but not the user's country.
    """
    # Create test data
    test_user = UserFactory()  # User is in Canada
    test_user.profile.country_code = "CA"  # User is in Canada
    test_user.save()
    product = ProductFactory()
    basket = BasketFactory(user=test_user, integrated_system=product.system)

    # Block the product for a different country (US)
    BlockedCountryFactory(country_code="US", product=product)

    # Call the function
    check_blocked_countries(basket, product)

    # No exception means the test passes


def test_get_redemption_type_one_time():
    """
    Test that get_redemption_type returns the correct redemption type for one-time discounts
    """
    kwargs = {"one_time": True}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_ONE_TIME


def test_get_redemption_type_once_per_user():
    """
    Test that get_redemption_type returns the correct redemption type for once-per-user discounts
    """
    kwargs = {"once_per_user": True}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_ONE_TIME_PER_USER


def test_get_redemption_type_specific_redemption_type():
    """
    Test that get_redemption_type returns the correct redemption type when a specific redemption type is provided
    """
    kwargs = {"redemption_type": REDEMPTION_TYPE_ONE_TIME}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_ONE_TIME

    kwargs = {"redemption_type": REDEMPTION_TYPE_ONE_TIME_PER_USER}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_ONE_TIME_PER_USER

    kwargs = {"redemption_type": REDEMPTION_TYPE_UNLIMITED}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_UNLIMITED


def test_get_redemption_type_invalid_redemption_type():
    """
    Test that get_redemption_type returns the default redemption type when an invalid redemption type is provided
    """
    kwargs = {"redemption_type": "INVALID_TYPE"}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_UNLIMITED


def test_get_redemption_type_no_kwargs():
    """
    Test that get_redemption_type returns the default redemption type when no kwargs are provided
    """
    kwargs = {}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_UNLIMITED


def test_get_redemption_type_multiple_kwargs():
    """
    Test that get_redemption_type returns the correct redemption type when multiple kwargs are provided
    """
    kwargs = {"one_time": True, "once_per_user": True}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_ONE_TIME

    kwargs = {"once_per_user": True, "redemption_type": REDEMPTION_TYPE_ONE_TIME}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_ONE_TIME_PER_USER


def test_get_redemption_type_unknown_redemption_type():
    """
    Test that get_redemption_type returns the default redemption type when an unknown redemption type is provided
    """
    kwargs = {"redemption_type": "UNKNOWN_TYPE"}
    assert get_redemption_type(kwargs) == REDEMPTION_TYPE_UNLIMITED


def test_get_users_with_valid_ids():
    """
    Test that get_users returns the correct users when valid user IDs are provided
    """
    # Create test users using UserFactory
    user1 = UserFactory()
    user2 = UserFactory()

    # Call the function with valid user IDs
    result = get_users([user1.id, user2.id])

    # Assert that the correct users are returned
    assert result == [user1, user2]


def test_get_users_with_valid_emails():
    """
    Test that get_users returns the correct users when valid user emails are provided
    """
    # Create test users using UserFactory
    user1 = UserFactory()
    user2 = UserFactory()

    # Call the function with valid user emails
    result = get_users([user1.email, user2.email])

    # Assert that the correct users are returned
    assert result == [user1, user2]


def test_get_users_with_mixed_identifiers():
    """
    Test that get_users returns the correct users when a mix of IDs and emails are provided
    """
    # Create test users using UserFactory
    user1 = UserFactory()
    user2 = UserFactory()

    # Call the function with a mix of IDs and emails
    result = get_users([user1.id, user2.email])

    # Assert that the correct users are returned
    assert result == [user1, user2]


def test_get_users_with_invalid_id():
    """
    Test that get_users raises an error when an invalid user ID is provided
    """
    # Create a test user
    test_user = UserFactory()

    # Call the function with an invalid ID
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        get_users([test_user.id + 1])  # Assuming this ID does not exist

    # Assert the correct error message
    assert str(exc_info.value) == f"User {test_user.id + 1} does not exist."


def test_get_users_with_invalid_email():
    """
    Test that get_users raises an error when an invalid user email is provided
    """
    # Create a test user
    UserFactory()

    # Call the function with an invalid email
    invalid_email = "nonexistent@example.com"
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        get_users([invalid_email])

    # Assert the correct error message
    assert str(exc_info.value) == f"User {invalid_email} does not exist."


def test_get_users_with_empty_list():
    """
    Test that get_users returns an empty list when an empty list is provided
    """
    # Call the function with an empty list
    result = get_users([])

    # Assert that the result is an empty list
    assert result == []


def test_get_users_with_string_ids():
    """
    Test that get_users returns the correct users when string representations of user IDs are provided
    """
    # Create a test user
    test_user = UserFactory()

    # Call the function with a string representation of the ID
    result = get_users([str(test_user.id)])

    # Assert that the correct user is returned
    assert result == [test_user]


def test_check_taxable_with_taxable_country():
    """
    Test that check_taxable applies a tax rate when the user's country code has a TaxRate.
    """
    # Create a TaxRate for a specific country code
    country_code = "US"
    taxrate = TaxRateFactory(country_code=country_code)

    # Create a Basket with a user whose country code matches the TaxRate
    basket = BasketFactory(user_blockable_country_code=country_code)

    # Call the function
    check_taxable(basket)

    # Refresh the basket instance from the database
    basket.refresh_from_db()

    # Assert that the tax rate was applied to the basket
    assert basket.tax_rate == taxrate


def test_check_taxable_with_non_taxable_country():
    """
    Test that check_taxable does not apply a tax rate when the user's country code does not have a TaxRate.
    """
    # Create a Basket with a user whose country code does not have a TaxRate
    country_code = "CA"
    basket = BasketFactory(user_blockable_country_code=country_code)

    # Call the function
    check_taxable(basket)

    # Refresh the basket instance from the database
    basket.refresh_from_db()

    # Assert that no tax rate was applied to the basket
    assert basket.tax_rate is None


def test_check_taxable_with_multiple_tax_rates():
    """
    Test that check_taxable applies the first matching tax rate to the basket when multiple TaxRate instances exist for the same country code.
    """
    # Create multiple TaxRate instances for the same country code
    country_code1 = "AB"
    country_code2 = "UK"
    taxrate1 = TaxRateFactory(country_code=country_code1)
    TaxRateFactory(country_code=country_code2)

    # Create a Basket with a user whose country code matches the TaxRate
    basket = BasketFactory(user_blockable_country_code=country_code1)

    # Call the function
    check_taxable(basket)

    # Refresh the basket instance from the database
    basket.refresh_from_db()

    # Assert that the first matching tax rate was applied to the basket
    assert basket.tax_rate == taxrate1


def test_check_taxable_with_no_tax_rates():
    """
    Test that check_taxable does not apply a tax rate when the user's country code has no TaxRate.
    """
    # Create a Basket with a user whose country code has no TaxRate
    country_code = "FR"
    basket = BasketFactory(user_blockable_country_code=country_code)

    # Call the function
    check_taxable(basket)

    # Refresh the basket instance from the database
    basket.refresh_from_db()

    # Assert that no tax rate was applied to the basket
    assert basket.tax_rate is None


def test_check_taxable_with_empty_country_code():
    """
    Test that check_taxable does not apply a tax rate when the user's country code is empty.
    """
    # Create a Basket with an empty country code
    basket = BasketFactory(user_blockable_country_code="")

    # Call the function
    check_taxable(basket)

    # Refresh the basket instance from the database
    basket.refresh_from_db()

    # Assert that no tax rate was applied to the basket
    assert basket.tax_rate is None
