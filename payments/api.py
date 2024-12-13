"""Ecommerce APIs"""

import logging
import uuid
from decimal import Decimal

import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.urls import reverse
from ipware import get_client_ip
from mitol.payment_gateway.api import CartItem as GatewayCartItem
from mitol.payment_gateway.api import Order as GatewayOrder
from mitol.payment_gateway.api import PaymentGateway, ProcessorResponse

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
from payments.models import (
    Basket,
    BlockedCountry,
    BulkDiscountCollection,
    Company,
    Discount,
    FulfilledOrder,
    Order,
    PendingOrder,
    TaxRate,
)
from payments.serializers.v0 import (
    WebhookBase,
    WebhookBaseSerializer,
    WebhookBasket,
    WebhookOrder,
)
from payments.tasks import dispatch_webhook
from payments.utils import parse_supplied_date
from system_meta.models import IntegratedSystem, Product
from unified_ecommerce.constants import (
    ALL_DISCOUNT_TYPES,
    ALL_PAYMENT_TYPES,
    ALL_REDEMPTION_TYPES,
    CYBERSOURCE_ACCEPT_CODES,
    CYBERSOURCE_ERROR_CODES,
    CYBERSOURCE_REASON_CODE_SUCCESS,
    DISCOUNT_TYPE_PERCENT_OFF,
    FLAGGED_COUNTRY_BLOCKED,
    FLAGGED_COUNTRY_TAX,
    POST_SALE_SOURCE_BACKOFFICE,
    POST_SALE_SOURCE_REDIRECT,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
    REFUND_SUCCESS_STATES,
    USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE,
    ZERO_PAYMENT_DATA,
)
from unified_ecommerce.utils import redirect_with_user_message
from users.api import determine_user_location, get_flagged_countries

log = logging.getLogger(__name__)
User = get_user_model()


def generate_checkout_payload(request, system):
    """Generate the payload to send to the payment gateway."""
    basket = Basket.establish_basket(request, system)

    # Notes for future implementation: this used to check for
    # * ~~Blocked products (by country)~~ (now handled in the basket_add hook)
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
        # Using the py-moneyed objects here for quantization.
        # It will do it correctly and then we get a Decimal out of it.
        gateway_order.items.append(
            GatewayCartItem(
                code=sku,
                name=field_dict["description"],
                quantity=1,
                sku=sku,
                unitprice=line_item.unit_price_money,
                taxable=line_item.tax_money,
            )
        )
        total_price += line_item.total_price

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


def send_post_sale_webhook(system_id, order_id, source):
    """
    Actually send the webhook some data for a post-sale event.

    This is split out so we can queue the webhook requests individually.
    """

    order = Order.objects.get(pk=order_id)
    system = IntegratedSystem.objects.get(pk=system_id)

    system_webhook_url = system.webhook_url
    if system_webhook_url:
        log.info(
            (
                "send_post_sale_webhook: Calling webhook endpoint %s for order %s "
                "with source %s"
            ),
            system_webhook_url,
            order.reference_number,
            source,
        )
    else:
        log.warning(
            (
                "send_post_sale_webhook: No webhook URL set for system %s, skipping"
                "for order %s"
            ),
            system.slug,
            order.reference_number,
        )
        return

    order_info = WebhookOrder(
        order=order,
        lines=[
            line
            for line in order.lines.all()
            if line.product.system.slug == system.slug
        ],
    )

    webhook_data = WebhookBase(
        type=PAYMENT_HOOK_ACTION_POST_SALE,
        system_slug=system.slug,
        system_key=system.api_key,
        user=order.purchaser,
        data=order_info,
    )

    dispatch_webhook.delay(system_webhook_url, WebhookBaseSerializer(webhook_data).data)


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

        send_post_sale_webhook(system.id, order.id, source)


def send_pre_sale_webhook(basket, product, action):
    """
    Send the webhook some data for a pre-sale event.

    This happens when a user adds an product to the cart.

    Args:
    - basket (Basket): the basket to work with
    - product (Product): the product being added/removed
    - action (WebhookBasketAction): The action being taken
    """

    system = basket.integrated_system

    basket_info = WebhookBasket(
        product=product,
        action=action,
    )

    system_webhook_url = system.webhook_url
    if system_webhook_url:
        log.info(
            "send_pre_sale_webhook: Calling webhook endpoint %s for %s",
            system_webhook_url,
            basket_info,
        )
    else:
        log.warning(
            (
                "send_pre_sale_webhook: No webhook URL set for system %s, skipping"
                "for event %s"
            ),
            system.slug,
            basket_info,
        )
        return

    webhook_data = WebhookBase(
        type=PAYMENT_HOOK_ACTION_PRE_SALE,
        system_slug=system.slug,
        system_key=system.api_key,
        user=basket.user,
        data=basket_info,
    )

    dispatch_webhook.delay(system_webhook_url, WebhookBaseSerializer(webhook_data).data)


def get_auto_apply_discounts_for_basket(basket_id: int) -> QuerySet[Discount]:
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


def generate_discount_code(**kwargs):  # noqa: C901, PLR0912, PLR0915
    """
    Generate a discount code (or a batch of discount codes) as specified by the
    arguments passed.

    Note that the prefix argument will not add any characters between it and the
    UUID - if you want one (the convention is a -), you need to ensure it's
    there in the prefix (and that counts against the limit)

    If you specify redemption_type, specifying one_time or one_time_per_user will not be
    honored.

    Keyword Args:
    * discount_type - one of the valid discount types
    * payment_type - one of the valid payment types
    * redemption_type - one of the valid redemption types (overrules use of the flags)
    * amount - the value of the discount
    * one_time - boolean; discount can only be redeemed once
    * one_time_per_user - boolean; discount can only be redeemed once per user
    * activates - date to activate
    * expires - date to expire the code
    * count - number of codes to create (requires prefix)
    * prefix - prefix to append to the codes (max 63 characters)
    * company - ID of the company to associate with the discount
    * transaction_number - transaction number to associate with the discount

    Returns:
    * List of generated codes, with the following fields:
      code, type, amount, expiration_date

    """
    codes_to_generate = []
    discount_type = kwargs["discount_type"]
    redemption_type = REDEMPTION_TYPE_UNLIMITED
    payment_type = kwargs["payment_type"]
    amount = Decimal(kwargs["amount"])
    bulk_discount_collection = None
    if kwargs["discount_type"] not in ALL_DISCOUNT_TYPES:
        raise ValueError(f"Invalid discount type: {kwargs['discount_type']}.")  # noqa: EM102, TRY003

    if payment_type not in ALL_PAYMENT_TYPES:
        raise ValueError(f"Payment type {payment_type} is not valid.")  # noqa: EM102, TRY003

    if kwargs["discount_type"] == DISCOUNT_TYPE_PERCENT_OFF and amount > 100:  # noqa: PLR2004
        message = (
            f"Discount amount {amount} not valid for discount type "
            f"{DISCOUNT_TYPE_PERCENT_OFF}."
        )
        raise ValueError(message)

    if kwargs["count"] > 1 and "prefix" not in kwargs:
        raise ValueError("You must specify a prefix to create a batch of codes.")  # noqa: EM101, TRY003

    if kwargs["count"] > 1:
        prefix = kwargs["prefix"]
        if prefix:
            # upped the discount code limit to 100 characters - this used to be 13 (50 - 37 for the UUID)  # noqa: E501
            if len(prefix) > 63:  # noqa: PLR2004
                raise ValueError(  # noqa: TRY003
                    f"Prefix {prefix} is {len(prefix)} - prefixes must be 63 characters or less."  # noqa: E501, EM102
                )
            bulk_discount_collection, _ = BulkDiscountCollection.objects.get_or_create(
                prefix=prefix
            )

        for i in range(kwargs["count"]):  # noqa: B007
            generated_uuid = uuid.uuid4()
            code = f"{prefix}{generated_uuid}"

            codes_to_generate.append(code)
    else:
        codes_to_generate = kwargs["codes"]

    if kwargs.get("one_time"):
        redemption_type = REDEMPTION_TYPE_ONE_TIME

    if kwargs.get("once_per_user"):
        redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER

    if (
        "redemption_type" in kwargs
        and kwargs["redemption_type"] in ALL_REDEMPTION_TYPES
    ):
        redemption_type = kwargs["redemption_type"]

    if "expires" in kwargs and kwargs["expires"] is not None:
        expiration_date = parse_supplied_date(kwargs["expires"])
    else:
        expiration_date = None

    if "activates" in kwargs and kwargs["activates"] is not None:
        activation_date = parse_supplied_date(kwargs["activates"])
    else:
        activation_date = None

    if "integrated_system" in kwargs and kwargs["integrated_system"] is not None:
        # Try to get the integrated system via ID or slug.  Raise an exception if it doesn't exist.  # noqa: E501
        # check if integrated_system is an integer or a slug
        integrated_system_missing_msg = (
            f"Integrated system {kwargs['integrated_system']} does not exist."
        )
        if kwargs["integrated_system"].isdigit():
            try:
                integrated_system = IntegratedSystem.objects.get(
                    pk=kwargs["integrated_system"]
                )
            except IntegratedSystem.DoesNotExist:
                raise ValueError(integrated_system_missing_msg)  # noqa: B904
        else:
            try:
                integrated_system = IntegratedSystem.objects.get(
                    slug=kwargs["integrated_system"]
                )
            except IntegratedSystem.DoesNotExist:
                raise ValueError(integrated_system_missing_msg)  # noqa: B904
    else:
        integrated_system = None

    if "product" in kwargs and kwargs["product"] is not None:
        # Try to get the product via ID or SKU.  Raise an exception if it doesn't exist.
        product_missing_msg = f"Product {kwargs['product']} does not exist."
        if kwargs["product"].isdigit():
            try:
                product = Product.objects.get(pk=kwargs["product"])
            except Product.DoesNotExist:
                raise ValueError(product_missing_msg)  # noqa: B904
        else:
            try:
                product = Product.objects.get(sku=kwargs["product"])
            except Product.DoesNotExist:
                raise ValueError(product_missing_msg)  # noqa: B904
    else:
        product = None

    if "users" in kwargs and kwargs["users"] is not None:
        # Try to get the users via ID or email.  Raise an exception if it doesn't exist.
        users = []
        user_missing_msg = "User %s does not exist."
        for user_identifier in kwargs["users"]:
            if user_identifier.isdigit():
                try:
                    users.append(User.objects.get(pk=user_identifier))
                except User.DoesNotExist:
                    raise ValueError(user_missing_msg % user_identifier)  # noqa: B904
            else:
                try:
                    user = User.objects.get(email=user_identifier)
                    users.append(user)
                except User.DoesNotExist:
                    raise ValueError(user_missing_msg % user_identifier)  # noqa: B904
    else:
        users = None

    if "company" in kwargs and kwargs["company"] is not None:
        try:
            company = Company.objects.get(pk=kwargs["company"])
        except Company.DoesNotExist:
            error_message = f"Company {kwargs['company']} does not exist."
            raise ValueError(error_message) from None
    else:
        company = None

    if "transaction_number" in kwargs and kwargs["transaction_number"] is not None:
        transaction_number = kwargs["transaction_number"]
    else:
        transaction_number = None

    generated_codes = []

    for code_to_generate in codes_to_generate:
        with reversion.create_revision():
            discount = Discount.objects.create(
                discount_type=discount_type,
                redemption_type=redemption_type,
                payment_type=payment_type,
                expiration_date=expiration_date,
                activation_date=activation_date,
                discount_code=code_to_generate,
                amount=amount,
                is_bulk=True,
                integrated_system=integrated_system,
                product=product,
                bulk_discount_collection=bulk_discount_collection,
                company=company,
                transaction_number=transaction_number,
            )
        if users:
            discount.assigned_users.set(users)

        generated_codes.append(discount)

    return generated_codes


def update_discount_codes(**kwargs):  # noqa: C901, PLR0912, PLR0915
    """
    Update a discount code (or a batch of discount codes) as specified by the
    arguments passed.

    Keyword Args:
    * discount_codes - list of discount codes to update
    * discount_type - one of the valid discount types
    * payment_type - one of the valid payment types
    * amount - the value of the discount
    * one_time - boolean; discount can only be redeemed once
    * one_time_per_user - boolean; discount can only be redeemed once per user
    * activates - date to activate
    * expires - date to expire the code
    * integrated_system - ID or slug of the integrated system to associate
      with the discount
    * product - ID or SKU of the product to associate with the discount
    * users - list of user IDs or emails to associate with the discount
    * clear_users - boolean; clear the users associated with the discount
    * clear_products - boolean; clear the products associated with the discount
    * clear_integrated_systems - boolean; clear the integrated systems associated with
      the discount
    * prefix - prefix of the bulk discount codes to update

    Returns:
    * Number of discounts updated

    """
    discount_codes_to_update = kwargs["discount_codes"]
    if kwargs.get("discount_type"):
        if kwargs["discount_type"] not in ALL_DISCOUNT_TYPES:
            error_message = f"Discount type {kwargs['discount_type']} is not valid."
            raise ValueError(error_message)
        else:
            discount_type = kwargs["discount_type"]
    else:
        discount_type = None

    if kwargs.get("payment_type"):
        if kwargs["payment_type"] not in ALL_PAYMENT_TYPES:
            error_message = f"Payment type {kwargs['payment_type']} is not valid."
            raise ValueError(error_message)
        else:
            payment_type = kwargs["payment_type"]
    else:
        payment_type = None

    if kwargs.get("one_time"):
        redemption_type = REDEMPTION_TYPE_ONE_TIME
    elif kwargs.get("one_time_per_user"):
        redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER
    else:
        redemption_type = REDEMPTION_TYPE_UNLIMITED

    amount = Decimal(kwargs["amount"]) if kwargs.get("amount") else None

    if kwargs.get("activates"):
        activation_date = parse_supplied_date(kwargs["activates"])
    else:
        activation_date = None

    if kwargs.get("expires"):
        expiration_date = parse_supplied_date(kwargs["expires"])
    else:
        expiration_date = None

    if kwargs.get("integrated_system"):
        # Try to get the integrated system via ID or slug.
        # Raise an exception if it doesn't exist.
        integrated_system_missing_msg = (
            f"Integrated system {kwargs['integrated_system']} does not exist."
        )
        if kwargs["integrated_system"].isdigit():
            try:
                integrated_system = IntegratedSystem.objects.get(
                    pk=kwargs["integrated_system"]
                )
            except IntegratedSystem.DoesNotExist:
                raise ValueError(integrated_system_missing_msg)  # noqa: B904
        else:
            try:
                integrated_system = IntegratedSystem.objects.get(
                    slug=kwargs["integrated_system"]
                )
            except IntegratedSystem.DoesNotExist:
                raise ValueError(integrated_system_missing_msg)  # noqa: B904
    else:
        integrated_system = None

    if kwargs.get("product"):
        if kwargs.get("clear_products"):
            error_message = "Cannot clear and set products at the same time."
            raise ValueError(error_message)
        # Try to get the product via ID or SKU.  Raise an exception if it doesn't exist.
        product_missing_msg = f"Product {kwargs['product']} does not exist."
        if kwargs["product"].isdigit():
            try:
                product = Product.objects.get(pk=kwargs["product"])
            except Product.DoesNotExist:
                raise ValueError(product_missing_msg)  # noqa: B904
        else:
            try:
                product = Product.objects.get(sku=kwargs["product"])
            except Product.DoesNotExist:
                raise ValueError(product_missing_msg)  # noqa: B904
    else:
        product = None

    if kwargs.get("users"):
        if kwargs.get("clear_users"):
            error_message = "Cannot clear and set users at the same time."
            raise ValueError(error_message)
        # Try to get the users via ID or email.  Raise an exception if it doesn't exist.
        users = []
        user_missing_msg = "User %s does not exist."
        for user_identifier in kwargs["users"]:
            if user_identifier.isdigit():
                try:
                    users.append(User.objects.get(pk=user_identifier))
                except User.DoesNotExist:
                    raise ValueError(user_missing_msg % user_identifier)  # noqa: B904
            else:
                try:
                    user = User.objects.get(email=user_identifier)
                    users.append(user)
                except User.DoesNotExist:
                    raise ValueError(user_missing_msg % user)  # noqa: B904
    else:
        users = None

    if kwargs.get("prefix"):
        prefix = kwargs["prefix"]
        bulk_discount_collection = BulkDiscountCollection.objects.filter(
            prefix=prefix
        ).first()
        if not bulk_discount_collection:
            error_message = (
                f"Bulk discount collection with prefix {prefix} does not exist."
            )
            raise ValueError(error_message)
        discounts_to_update = bulk_discount_collection.discounts.all()
    else:
        discounts_to_update = Discount.objects.filter(
            discount_code__in=discount_codes_to_update
        )

    # Don't include any discounts with one time or one time per user redemption types
    # if there is a matching RedeemedDiscount, or if the max_redemptions
    # has been reached.
    for discount in discounts_to_update:
        if discount.redemption_type in [
            REDEMPTION_TYPE_ONE_TIME,
            REDEMPTION_TYPE_ONE_TIME_PER_USER,
        ]:
            if discount.redeemed_discounts.exists():
                discounts_to_update = discounts_to_update.exclude(pk=discount.pk)
        elif (
            discount.max_redemptions
            and discount.redeemed_discounts.count() == discount.max_redemptions
        ):
            discounts_to_update = discounts_to_update.exclude(pk=discount.pk)

    discount_attributes_dict = {
        "discount_type": discount_type,
        "redemption_type": redemption_type,
        "payment_type": payment_type,
        "expiration_date": expiration_date,
        "activation_date": activation_date,
        "amount": amount,
        "integrated_system": integrated_system,
        "product": product,
    }
    discount_values_to_update = {
        key: value
        for key, value in discount_attributes_dict.items()
        if value is not None
    }
    with reversion.create_revision():
        number_of_discounts_updated = discounts_to_update.update(
            **discount_values_to_update,
        )
        if kwargs.get("clear_products"):
            discounts_to_update.update(product=None)
        if kwargs.get("clear_integrated_systems"):
            discounts_to_update.update(integrated_system=None)
    if kwargs.get("clear_users"):
        for discount in discounts_to_update:
            discount.assigned_users.clear()
    elif users:
        for discount in discounts_to_update:
            discount.assigned_users.set(users)

    return number_of_discounts_updated


def locate_customer_for_basket(request, basket, basket_item):
    """
    Locate the customer.

    For the basket_add hook, we need to figure out where the customer is and
    write that data to the basket so it can be used for later checks. This does
    not enforce the check - but for blocked countries we need to consider
    blockages that may be product-specific, so we need to know that.

    Args:
    - request (HttpRequest): the current request
    - basket (Basket): the current basket
    - basket_item (Product): the item to add to the basket
    Returns:
    - None
    """

    log.debug(
        "locate_customer_for_basket: running for %s at %s",
        request.user,
        get_client_ip(request),
    )

    location_meta = CustomerLocationMetadata(
        determine_user_location(
            request,
            get_flagged_countries(FLAGGED_COUNTRY_BLOCKED, product=basket_item),
        ),
        determine_user_location(request, get_flagged_countries(FLAGGED_COUNTRY_TAX)),
    )

    basket.set_customer_location(location_meta)
    basket.save()


def check_blocked_countries(basket, basket_item):
    """
    Check to see if the product is blocked for this customer.

    We should have the customer's location stored, so now perform the check
    to see if the product is blocked or not. If it is, we raise an exception
    to stop the process.

    Try this one first so we can kick the user out if they're blocked.

    Args:
    - basket (Basket): the current basket
    - basket_item (Product): the item to add to the basket
    Returns:
    - None
    Raises:
    - ProductBlockedError: if the customer is blocked
    """

    log.debug("check_blocked_countries: checking for blockages for %s", basket.user)

    blocked_qset = BlockedCountry.objects.filter(
        country_code=basket.user_blockable_country_code
    ).filter(Q(product__isnull=True) | Q(product=basket_item))

    if blocked_qset.exists():
        log.debug("check_blocked_countries: user is blocked")
        errmsg = "Product %s blocked from purchase in country %s"
        raise ProductBlockedError(
            errmsg, basket_item, basket.user_blockable_country_code
        )


def check_taxable(basket):
    """
    Check to see if the product is taxable for this customer.

    We don't consider particular items taxable or not but we may want to
    change that in the future. (Maybe one day we'll sell gift cards or
    something!) So, this really applies to the basket - if there's an
    applicable rate, then we tack it on to the basket.

    Args:
    - basket (Basket): the current basket
    Returns:
    - None
    """

    log.debug("check_taxable: checking for tax for %s", basket.user)

    taxable_qset = TaxRate.objects.filter(
        country_code=basket.user_blockable_country_code
    )

    if taxable_qset.exists():
        taxrate = taxable_qset.first()
        basket.tax_rate = taxrate
        basket.save()
        log.debug("check_taxable: charging the tax for %s", taxrate)
