"""Ecommerce APIs"""

import logging
import uuid
from decimal import Decimal

import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
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
    ZERO_PAYMENT_DATA,
)
from users.api import determine_user_location, get_flagged_countries

log = logging.getLogger(__name__)
User = get_user_model()


def generate_checkout_payload(request, system):
    """Generate the payload to send to the payment gateway."""
    basket = Basket.establish_basket(request, system)

    log.debug("established basket has %s lines", basket.basket_items.count())

    # Notes for future implementation: this used to check for
    # * Re-purchases of the same product
    # * Purchasing a product that is expired
    # These are all cleared for now, but will need to go back here later.

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
        error_message = "Could not validate response from the payment processor."
        raise PermissionDenied(error_message)

    processor_response = PaymentGateway.get_formatted_response(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
    )
    reason_code = (
        int(processor_response.response_code)
        if (
            processor_response.response_code
            and processor_response.response_code.isdigit()
        )
        else None
    )
    transaction_id = processor_response.transaction_id

    # Log transaction status
    if reason_code is not None:
        message = (
            f"Transaction ID: {transaction_id}, Reason Code: {reason_code}, "
            f"Message: {processor_response.message}"
        )
        if reason_code in CYBERSOURCE_ERROR_CODES:
            log.error("Transaction was not successful. %s", message)
        elif reason_code not in CYBERSOURCE_ACCEPT_CODES:
            log.debug("Transaction was not successful. %s", message)

    # Handle processor response states
    state_handlers = {
        ProcessorResponse.STATE_DECLINED: order.decline,
        ProcessorResponse.STATE_ERROR: order.errored,
        ProcessorResponse.STATE_CANCELLED: order.cancel,
        ProcessorResponse.STATE_REVIEW: order.cancel,
        ProcessorResponse.STATE_ACCEPTED: lambda: fulfill_completed_order(
            order,
            request.POST,
            Basket.objects.filter(user=order.purchaser).first(),
            source,
        ),
    }

    if processor_response.state in state_handlers:
        log.debug(
            "Transaction %s: %s",
            processor_response.state.lower(),
            processor_response.message,
        )
        state_handlers[processor_response.state]()
    elif reason_code == CYBERSOURCE_REASON_CODE_SUCCESS:
        log.debug("Transaction accepted!: %s", processor_response.message)
        fulfill_completed_order(
            order,
            request.POST,
            Basket.objects.filter(user=order.purchaser).first(),
            source,
        )
    else:
        log.error(
            "Unknown state %s found: transaction ID %s, reason code %s, "
            "response message %s",
            processor_response.state,
            transaction_id,
            reason_code,
            processor_response.message,
        )
        order.cancel()

    return order.state


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
    # Validate input
    if not any([order_id, reference_number]):
        log.error("Either order_id or reference_number is required to fetch the Order.")
        return (
            False,
            "Either order_id or reference_number is required to fetch the Order.",
        )

    # Fetch the order
    try:
        order = (
            FulfilledOrder.objects.get(reference_number=reference_number)
            if reference_number
            else FulfilledOrder.objects.get(pk=order_id)
        )
    except FulfilledOrder.DoesNotExist:
        log.exception(
            "Order with %s %s not found.",
            "reference_number" if reference_number else "order_id",
            reference_number or order_id,
        )
        raise

    # Validate order state
    if order.state != Order.STATE.FULFILLED:
        log.error("Order with order_id %s is not in fulfilled state.", order.id)
        return False, f"Order with order_id {order.id} is not in fulfilled state."

    # Fetch the most recent transaction
    order_recent_transaction = order.transactions.first()
    if not order_recent_transaction:
        log.error("There is no associated transaction against order_id %s", order.id)
        return False, f"There is no associated transaction against order_id {order.id}"

    # Check for PayPal payment
    if "paypal_token" in order_recent_transaction.data:
        msg = (
            f"PayPal: Order {order.reference_number} contains a PayPal"
            "transaction. Please contact Finance to refund this order."
        )
        raise PaypalRefundError(msg)

    # Prepare refund request
    transaction_dict = order_recent_transaction.data
    if "refund_amount" in kwargs:
        transaction_dict["req_amount"] = kwargs["refund_amount"]

    # Process refund
    refund_gateway_request = PaymentGateway.create_refund_request(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, transaction_dict
    )
    response = PaymentGateway.start_refund(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, refund_gateway_request
    )

    # Handle refund response
    if response.state not in REFUND_SUCCESS_STATES:
        log.error(
            "There was an error with the Refund API request: %s", response.message
        )
        error_message = f"Payment gateway returned an error: {response.message}"
        raise PaymentGatewayError(error_message)

    # Record successful refund
    order.refund(
        api_response_data=response.response_data,
        amount=transaction_dict["req_amount"],
        reason=kwargs.get("refund_reason", ""),
    )
    return True, ""


def send_post_sale_webhook(system_id, order_id, source):
    """
    Actually send the webhook some data for a post-sale event.

    This is split out so we can queue the webhook requests individually.
    """

    order = Order.objects.get(pk=order_id)
    system = IntegratedSystem.objects.get(pk=system_id)

    system_webhook_url = system.webhook_url
    if not system.webhook_url:
        log.warning(
            "send_post_sale_webhook: No webhook URL set for system %s, "
            "skipping for order %s",
            system.slug,
            order.reference_number,
        )
        return

    log.info(
        "send_post_sale_webhook: Calling webhook endpoint %s for order %s "
        "with source %s",
        system.webhook_url,
        order.reference_number,
        source,
    )

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

    # Extract unique systems from the order lines
    systems = {
        line.product_version._object_version.object.system  # noqa: SLF001
        for line in order.lines.all()
        if line.product_version and line.product_version._object_version  # noqa: SLF001
    }

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
    products = basket.get_products()

    return Discount.objects.filter(
        Q(product__in=products) | Q(product__isnull=True),
        Q(integrated_system=basket.integrated_system)
        | Q(integrated_system__isnull=True),
        Q(assigned_users=basket.user) | Q(assigned_users__isnull=True),
        automatic=True,
    )


def validate_discount_type(discount_type):
    """
    Validate the discount type.

    Args:
        discount_type (str): The discount type to validate.

    Raises:
        ValueError: If the discount type is not valid.
    """
    if discount_type not in ALL_DISCOUNT_TYPES:
        error_message = f"Invalid discount type: {discount_type}."
        raise ValueError(error_message)


def validate_payment_type(payment_type):
    """
    Validate the payment type.

    Args:
        payment_type (str): The payment type to validate.

    Raises:
        ValueError: If the payment type is not valid.
    """
    if payment_type not in ALL_PAYMENT_TYPES:
        error_message = f"Payment type {payment_type} is not valid."
        raise ValueError(error_message)


def validate_percent_off_amount(discount_type, amount):
    """
    Validate the percent off amount.

    Args:
        discount_type (str): discount type.
        amount (int): discount amount.

    Raises:
        ValueError: If the discount amount is not valid for the discount type.
    """
    MAX_PERCENT_OFF_AMOUNT = 100
    if discount_type == DISCOUNT_TYPE_PERCENT_OFF and amount > MAX_PERCENT_OFF_AMOUNT:
        error_message = (
            f"Discount amount {amount} not valid for discount type "
            f"{DISCOUNT_TYPE_PERCENT_OFF}."
        )
        raise ValueError(error_message)


def validate_prefix_for_batch(count, prefix):
    """
    Validate the prefix for a batch of discount codes.

    Args:
        count (int): The number of codes to create.
        prefix (str): The prefix to append to the codes.

    Raises:
        ValueError: If the prefix is not valid for a batch of codes.
        ValueError: If the prefix is too long.
    """
    MAX_PREFIX_LENGTH = 63
    if count > 1 and not prefix:
        error_message = "You must specify a prefix to create a batch of codes."
        raise ValueError(error_message)
    if prefix and len(prefix) > MAX_PREFIX_LENGTH:
        message = (
            f"Prefix {prefix} is {len(prefix)} - prefixes must be "
            "63 characters or less."
        )
        raise ValueError(message)


def generate_codes(count, prefix=None, codes=None):
    """
    Generate a list of discount codes.

    Args:
        count (int): The number of codes to create.
        prefix (str, optional): The prefix to append to the codes. Defaults to None.
        codes (str, optional): The codes to create. Defaults to None.

    Returns:
        list(str): The generated codes.
    """
    if count > 1:
        return [f"{prefix}{uuid.uuid4()}" for _ in range(count)]
    return [codes]


def get_redemption_type(kwargs):
    """
    Get the redemption type.

    Args:
        kwargs (): The keyword arguments passed to the function.
        one_time, once_per_user, and redemption_type are the valid arguments.

    """
    if kwargs.get("one_time"):
        return REDEMPTION_TYPE_ONE_TIME
    if kwargs.get("once_per_user"):
        return REDEMPTION_TYPE_ONE_TIME_PER_USER
    if (
        "redemption_type" in kwargs
        and kwargs["redemption_type"] in ALL_REDEMPTION_TYPES
    ):
        return kwargs["redemption_type"]
    return REDEMPTION_TYPE_UNLIMITED


def get_object_or_raise(model, identifier, missing_msg):
    """
    Get an object from the model, or raise an error if it doesn't exist.

    Args:
        model (Model): The model to get the object from.
        identifier (): The identifier of the object.
        missing_msg (str): The message to raise if the object doesn't exist.

    Raises:
        ValueError: If the object doesn't exist.

    Returns:
        Model: The object from the model.
    """
    try:
        if isinstance(identifier, int) or (
            isinstance(identifier, str) and identifier.isdigit()
        ):
            return model.objects.get(pk=identifier)
        return model.objects.get(slug=identifier)
    except ObjectDoesNotExist as err:
        raise ValueError(missing_msg) from err


def get_users(users):
    """
    Get a list of users from the user identifiers.

    Args:
        users (str): The user identifiers.

    Raises:
        ValueError: If the user doesn't exist.

    Returns:
        User: The list of users.
    """
    user_list = []
    for user_identifier in users:
        try:
            if isinstance(user_identifier, int) or (
                isinstance(user_identifier, str) and user_identifier.isdigit()
            ):
                user_list.append(User.objects.get(pk=user_identifier))
            else:
                user_list.append(User.objects.get(email=user_identifier))
        except ObjectDoesNotExist:
            error_message = f"User {user_identifier} does not exist."
            raise ValueError(error_message) from None
    return user_list


def generate_discount_code(**kwargs):
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
    * automatic - boolean; discount is automatically applied

    Returns:
    * List of generated codes, with the following fields:
      code, type, amount, expiration_date

    """
    validate_discount_type(kwargs["discount_type"])
    validate_payment_type(kwargs["payment_type"])
    validate_percent_off_amount(kwargs["discount_type"], Decimal(kwargs["amount"]))
    validate_prefix_for_batch(kwargs.get("count", 1), kwargs.get("prefix", ""))

    codes_to_generate = generate_codes(
        kwargs.get("count", 1), kwargs.get("prefix", ""), kwargs.get("codes", "")
    )
    redemption_type = get_redemption_type(kwargs)
    expiration_date = (
        parse_supplied_date(kwargs["expires"]) if kwargs.get("expires") else None
    )
    activation_date = (
        parse_supplied_date(kwargs["activates"]) if kwargs.get("activates") else None
    )

    automatic = kwargs.get("automatic", False)

    integrated_system = (
        get_object_or_raise(
            IntegratedSystem,
            kwargs["integrated_system"],
            f"Integrated system {kwargs['integrated_system']} does not exist.",
        )
        if kwargs.get("integrated_system")
        else None
    )

    product = (
        get_object_or_raise(
            Product, kwargs["product"], f"Product {kwargs['product']} does not exist."
        )
        if kwargs.get("product")
        else None
    )

    users = get_users(kwargs["users"]) if kwargs.get("users") else None

    company = (
        get_object_or_raise(
            Company, kwargs["company"], f"Company {kwargs['company']} does not exist."
        )
        if kwargs.get("company")
        else None
    )

    transaction_number = kwargs.get("transaction_number", "")

    generated_codes = []
    for code in codes_to_generate:
        with reversion.create_revision():
            discount = Discount.objects.create(
                discount_type=kwargs["discount_type"],
                redemption_type=redemption_type,
                payment_type=kwargs["payment_type"],
                expiration_date=expiration_date,
                activation_date=activation_date,
                discount_code=code,
                amount=Decimal(kwargs["amount"]),
                is_bulk=True,
                integrated_system=integrated_system,
                product=product,
                bulk_discount_collection=(
                    BulkDiscountCollection.objects.get_or_create(
                        prefix=kwargs.get("prefix")
                    )[0]
                    if kwargs.get("prefix")
                    else None
                ),
                company=company,
                transaction_number=transaction_number,
                automatic=automatic,
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
    if kwargs.get("discount_type"):
        validate_discount_type(kwargs["discount_type"])
        discount_type = kwargs["discount_type"]
        if kwargs.get("amount"):
            validate_percent_off_amount(discount_type, Decimal(kwargs["amount"]))
    else:
        discount_type = None

    if kwargs.get("payment_type"):
        validate_payment_type(kwargs["payment_type"])
        payment_type = kwargs["payment_type"]
    else:
        payment_type = None

    redemption_type = get_redemption_type(kwargs)

    amount = Decimal(kwargs["amount"]) if kwargs.get("amount") else None

    if kwargs.get("activates"):
        activation_date = parse_supplied_date(kwargs["activates"])
    else:
        activation_date = None

    if kwargs.get("expires"):
        expiration_date = parse_supplied_date(kwargs["expires"])
    else:
        expiration_date = None

    integrated_system = (
        get_object_or_raise(
            IntegratedSystem,
            kwargs["integrated_system"],
            f"Integrated system {kwargs['integrated_system']} does not exist.",
        )
        if kwargs.get("integrated_system")
        else None
    )

    product = (
        get_object_or_raise(
            Product, kwargs["product"], f"Product {kwargs['product']} does not exist."
        )
        if kwargs.get("product")
        else None
    )

    users = get_users(kwargs["users"]) if kwargs.get("users") else None

    if kwargs.get("prefix"):
        prefix = kwargs.get("prefix")
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
        discount_codes_to_update = kwargs.get("discount_codes", [])
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
    Check if the product is blocked for the customer based on their location.
    Raises ProductBlockedError if the product is blocked.

    Args:
    - basket (Basket): The current basket.
    - basket_item (Product): The item to add to the basket.
    Raises:
    - ProductBlockedError: If the customer is blocked from purchasing the product.
    """
    log.debug("Checking blockages for user: %s", basket.user)

    if (
        BlockedCountry.objects.filter(
            country_code=basket.user_blockable_country_code,
        )
        .filter(Q(product__isnull=True) | Q(product=basket_item))
        .exists()
    ):
        log.debug("User is blocked from purchasing the product.")
        message = (
            f"Product {basket_item} blocked in country "
            f"{basket.user_blockable_country_code}"
        )
        raise ProductBlockedError(message)


def check_taxable(basket):
    """
    Check if the basket is taxable based on the user's country code.
    If taxable, apply the tax rate to the basket.

    Args:
    - basket (Basket): the current basket
    Returns:
    - None
    """
    log.debug("check_taxable: checking for tax for %s", basket.user)

    taxrate = TaxRate.objects.filter(
        country_code=basket.user_blockable_country_code
    ).first()

    if taxrate:
        basket.tax_rate = taxrate
        basket.save()
        log.debug("check_taxable: charging the tax for %s", taxrate)
