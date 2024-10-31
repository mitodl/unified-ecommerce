"""Ecommerce APIs"""

import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from ipware import get_client_ip
from mitol.payment_gateway.api import CartItem as GatewayCartItem
from mitol.payment_gateway.api import Order as GatewayOrder
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse

from payments.exceptions import PaymentGatewayError, PaypalRefundError
from payments.models import (
    Basket,
    Discount,
    FulfilledOrder,
    Order,
    PendingOrder,
)
from payments.tasks import send_post_sale_webhook
from system_meta.models import IntegratedSystem
from unified_ecommerce.constants import (
    CYBERSOURCE_ACCEPT_CODES,
    CYBERSOURCE_ERROR_CODES,
    CYBERSOURCE_REASON_CODE_SUCCESS,
    POST_SALE_SOURCE_BACKOFFICE,
    POST_SALE_SOURCE_REDIRECT,
    REFUND_SUCCESS_STATES,
    USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
    ZERO_PAYMENT_DATA,
)
from unified_ecommerce.utils import redirect_with_user_message

log = logging.getLogger(__name__)


def generate_checkout_payload(request, system):
    """Generate the payload to send to the payment gateway."""
    basket = Basket.establish_basket(request, system)

    # Notes for future implementation: this used to check for
    # * Blocked products (by country)
    # * Re-purchases of the same product
    # * Purchasing a product that is expired
    # These are all cleared for now, but will need to go back here later.
    # For completeness, this is also where discounts were checked for validity.

    order = PendingOrder.create_from_basket(basket)
    total_price = 0

    ip = get_client_ip(request)[0]

    gateway_order = GatewayOrder(
        username=request.user.username,
        ip_address=ip,
        reference=order.reference_number,
        items=[],
    )

    for line_item in order.lines.all():
        log.debug("Adding line item %s", line_item)
        field_dict = line_item.product_version.field_dict
        system = IntegratedSystem.objects.get(pk=field_dict["system_id"])
        sku = f"{system.slug}!{field_dict['sku']}"
        gateway_order.items.append(
            GatewayCartItem(
                code=sku,
                name=field_dict["description"],
                quantity=1,
                sku=sku,
                unitprice=line_item.discounted_price,
                taxable=0,
            )
        )
        total_price += line_item.discounted_price

    if total_price == 0:
        with transaction.atomic():
            fulfill_completed_order(
                order, payment_data=ZERO_PAYMENT_DATA, basket=basket
            )
            return {
                "no_checkout": True,
                "response": redirect_with_user_message(
                    reverse("cart"),
                    {
                        "type": USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
                        "run": order.lines.first().purchased_object.course.title,
                    },
                ),
            }

    callback_uri = request.build_absolute_uri(reverse("v0:checkout-result-callback"))

    log.debug("Gateway order for %s: %s", order.reference_number, gateway_order)

    return PaymentGateway.start_payment(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        gateway_order,
        callback_uri,
        callback_uri,
        merchant_fields=[basket.id],
    )


def fulfill_completed_order(
    order,
    payment_data,
    basket=None,
    source=POST_SALE_SOURCE_BACKOFFICE,  # noqa: ARG001
):
    """Fulfill the order."""
    order.fulfill(payment_data)

    if basket and basket.compare_to_order(order):
        basket.delete()


def get_order_from_cybersource_payment_response(request):
    """Figure out the order from the payment response from Cybersource."""
    payment_data = request.POST
    converted_order = PaymentGateway.get_gateway_class(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
    ).convert_to_order(payment_data)
    order_id = Order.decode_reference_number(converted_order.reference)

    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except ObjectDoesNotExist:
        order = None
    return order


def process_cybersource_payment_response(
    request, order, source=POST_SALE_SOURCE_REDIRECT
):
    """
    Update the order and basket based on the payment request from Cybersource.
    Returns the order state after applying update operations corresponding to
    the request.

    Args:
        - request (HttpRequest): The payment request received from Cybersource.
        - order (Order): The order corresponding to the request payload.
    Returns:
        Order.state
    """

    if not PaymentGateway.validate_processor_response(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    ):
        msg = "Could not validate response from the payment processor."
        raise PermissionDenied(msg)

    processor_response = PaymentGateway.get_formatted_response(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    )

    reason_code = processor_response.response_code
    transaction_id = processor_response.transaction_id
    if reason_code and reason_code.isdigit():
        reason_code = int(reason_code)
        message = (
            "Transaction was not successful. "
            "Transaction ID:%s  Reason Code:%d  Message:%s"
        )
        if reason_code in CYBERSOURCE_ERROR_CODES:
            # Log the errors as errors, so they make Sentry logs.
            log.error(message, transaction_id, reason_code, processor_response.message)
        elif reason_code not in CYBERSOURCE_ACCEPT_CODES:
            # These may be declines or reviews - only log in debug mode.
            log.debug(message, transaction_id, reason_code, processor_response.message)

    return_message = ""

    if processor_response.state == ProcessorResponse.STATE_DECLINED:
        # Transaction declined for some reason
        # This probably means the order needed to go through the process
        # again so maybe tell the user to do a thing.
        msg = f"Transaction declined: {processor_response.message}"
        log.debug(msg)
        order.decline()
        return_message = order.state
    elif processor_response.state == ProcessorResponse.STATE_ERROR:
        # Error - something went wrong with the request
        msg = f"Error happened submitting the transaction: {processor_response.message}"
        log.debug(msg)
        order.errored()
        return_message = order.state
    elif processor_response.state in [
        ProcessorResponse.STATE_CANCELLED,
        ProcessorResponse.STATE_REVIEW,
    ]:
        # Transaction cancelled or reviewed
        # Transaction could be cancelled for reasons that don't necessarily
        # mean that the entire order is invalid, so we'll do nothing with
        # the order here (other than set it to Cancelled).
        # Transaction could be
        msg = f"Transaction cancelled/reviewed: {processor_response.message}"
        log.debug(msg)
        order.cancel()
        return_message = order.state

    elif (
        processor_response.state == ProcessorResponse.STATE_ACCEPTED
        or reason_code == CYBERSOURCE_REASON_CODE_SUCCESS
    ):
        # It actually worked here
        basket = Basket.objects.filter(user=order.purchaser).first()
        try:
            msg = f"Transaction accepted!: {processor_response.message}"
            log.debug(msg)
            fulfill_completed_order(order, request.POST, basket, source)
        except ValidationError:
            msg = (
                "Missing transaction id from transaction response: "
                f"{processor_response.message}"
            )
            log.debug(msg)
            raise

        return_message = order.state
    else:
        msg = (
            f"Unknown state {processor_response.state} found: transaction ID"
            f"{transaction_id}, reason code {reason_code}, response message"
            f" {processor_response.message}"
        )
        log.error(msg)
        order.cancel()
        return_message = order.state

    return return_message


def refund_order(
    *, order_id: int | None = None, reference_number: str | None = None, **kwargs
):
    """
    Refund the specified order.

    Args:
       order_id (int): ID of the order which is being refunded
       reference_number (str): Reference number of the order
       kwargs (dict): Dictionary of the other attributes that are passed e.g.
       refund amount, refund reason
       If no refund_amount is provided it will use refund amount from
       Transaction obj

    Returns:
        tuple of (bool, str) : A boolean identifying if an order refund was
        successful, and the error message (if there is one)
    """
    refund_amount = kwargs.get("refund_amount")
    refund_reason = kwargs.get("refund_reason", "")
    message = ""
    if reference_number is not None:
        order = FulfilledOrder.objects.get(reference_number=reference_number)
    elif order_id is not None:
        order = FulfilledOrder.objects.get(pk=order_id)
    else:
        message = "Either order_id or reference_number is required to fetch the Order."
        log.error(message)
        return False, message
    if order.state != Order.STATE.FULFILLED:
        message = f"Order with order_id {order.id} is not in fulfilled state."
        log.error(message)
        return False, message

    order_recent_transaction = order.transactions.first()

    if not order_recent_transaction:
        message = f"There is no associated transaction against order_id {order.id}"
        log.error(message)
        return False, message

    transaction_dict = order_recent_transaction.data

    # Check for a PayPal payment - if there's one, we can't process it
    if "paypal_token" in transaction_dict:
        msg = (
            f"PayPal: Order {order.reference_number} contains a PayPal"
            "transaction. Please contact Finance to refund this order."
        )
        raise PaypalRefundError(msg)

    # The refund amount can be different then the payment amount, so we override
    # that before PaymentGateway processing.
    # e.g. While refunding order from Django Admin we can select custom amount.
    if refund_amount:
        transaction_dict["req_amount"] = refund_amount

    refund_gateway_request = PaymentGateway.create_refund_request(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, transaction_dict
    )

    response = PaymentGateway.start_refund(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        refund_gateway_request,
    )

    if response.state in REFUND_SUCCESS_STATES:
        # Record refund transaction with PaymentGateway's refund response
        order.refund(
            api_response_data=response.response_data,
            amount=transaction_dict["req_amount"],
            reason=refund_reason,
        )
    else:
        log.error(
            "There was an error with the Refund API request %s",
            response.message,
        )
        # PaymentGateway didn't raise an exception and instead gave a
        # Response but the response status was not success so we manually
        # rollback the transaction in this case.
        msg = f"Payment gateway returned an error: {response.message}"
        raise PaymentGatewayError(msg)

    return True, message


def check_and_process_pending_orders_for_resolution(refnos=None):
    """
    Check pending orders for resolution. By default, this will pull all the
    pending orders that are in the system.

    Args:
    - refnos (list or None): check specific reference numbers
    Returns:
    - Tuple of counts: fulfilled count, cancelled count, error count

    """

    gateway = PaymentGateway.get_gateway_class(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY
    )

    if refnos is not None:
        pending_orders = PendingOrder.objects.filter(
            state=PendingOrder.STATE.PENDING, reference_number__in=refnos
        ).values_list("reference_number", flat=True)
    else:
        pending_orders = PendingOrder.objects.filter(
            state=PendingOrder.STATE.PENDING
        ).values_list("reference_number", flat=True)

    if len(pending_orders) == 0:
        return (0, 0, 0)

    msg = f"Resolving {len(pending_orders)} orders"
    log.info(msg)

    results = gateway.find_and_get_transactions(pending_orders)

    if len(results.keys()) == 0:
        msg = "No orders found to resolve."
        log.info(msg)
        return (0, 0, 0)

    fulfilled_count = cancel_count = error_count = 0

    for result in results:
        payload = results[result]
        if int(payload["reason_code"]) == CYBERSOURCE_REASON_CODE_SUCCESS:
            try:
                order = PendingOrder.objects.filter(
                    state=PendingOrder.STATE.PENDING,
                    reference_number=payload["req_reference_number"],
                ).get()

                order.fulfill(payload)
                fulfilled_count += 1

                msg = f"Fulfilled order {order.reference_number}."
                log.info(msg)
            except Exception as e:
                msg = (
                    "Couldn't process pending order for fulfillment "
                    f"{payload['req_reference_number']}: {e!s}"
                )
                log.exception(msg)
                error_count += 1
        else:
            try:
                order = PendingOrder.objects.filter(
                    state=PendingOrder.STATE.PENDING,
                    reference_number=payload["req_reference_number"],
                ).get()

                order.cancel()
                order.transactions.create(
                    transaction_id=payload["transaction_id"],
                    amount=order.total_price_paid,
                    data=payload,
                    reason=f"Cancelled due to processor code {payload['reason_code']}",
                )
                order.save()
                cancel_count += 1

                msg = f"Cancelled order {order.reference_number}."
                log.info(msg)
            except Exception:
                msg = "Couldn't process pending order for cancellation %s"
                log.exception(msg, payload["req_reference_number"])
                error_count += 1

    return (fulfilled_count, cancel_count, error_count)


def process_post_sale_webhooks(order_id, source):
    """
    Send data to the webhooks for post-sale events.

    If the system in question doesn't have a webhook URL, we will skip it.
    """

    log.info("Queueing webhook endpoints for order %s with source %s", order_id, source)

    order = Order.objects.prefetch_related("lines", "lines__product_version").get(
        pk=order_id
    )

    systems = [
        product.system
        for product in [
            line.product_version._object_version.object  # noqa: SLF001
            for line in order.lines.all()
        ]
    ]

    for system in systems:
        if not system.webhook_url:
            log.warning("No webhook URL specified for system %s", system.slug)
            continue

        send_post_sale_webhook.delay(system.id, order.id, source)


def get_auto_apply_discounts_for_basket(basket_id):
    """
    Get the auto-apply discounts that can be applied to a basket.

    Args:
        basket_id (int): The ID of the basket to get the auto-apply discounts for.

    Returns:
        QuerySet: The auto-apply discounts that can be applied to the basket.
    """
    basket = Basket.objects.get(pk=basket_id)
    return (
        Discount.objects.filter(
            Q(product__in=basket.get_products()) | Q(product__isnull=True)
        )
        .filter(
            Q(integrated_system=basket.integrated_system)
            | Q(integrated_system__isnull=True)
        )
        .filter(Q(assigned_users=basket.user) | Q(assigned_users__isnull=True))
        .filter(automatic=True)
    )
