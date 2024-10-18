"""Hookspecs for the payments app."""
# ruff: noqa: ARG001

import pluggy

hookspec = pluggy.HookspecMarker("unified_ecommerce")


@hookspec
def basket_add(basket_id: int, basket_item: int):
    """
    Complete actions that need to be taken when items are added to the basket.

    When a user adds an item to the basket, we'll want to be able to make some
    decisions or do some processing. This will usually fall into these categories:
    - Eligibility: we'll need to make sure the user is allowed to purchase the
      item in question.
    - Tax assessment: we'll need to make sure the user is charged tax for the
      item if they happen to be in a locale that requires us to collect it.
    - Discount application: we may have a discount code that should apply to the
      user, system, and item combination being added. If so, we'll need to apply
      that discount.
    - Enrollment: some systems automatically grant an enrollment for users when
      they simply add the item to the basket, so we should alert the system when
      the item is added. (MITx Online does this - adding to basket should
      automatically create an audit enrollment in the course/program.)

    Args:
    basket_id (int): the ID of the basket the item is being added to
    basket_item (int): the ID of the item that will be added
    """


@hookspec
def pre_sale(basket_id: int):
    """
    Complete actions that need to be taken before the basket turns into an order.

    This event will fire before the basket is about to be transformed into an
    order (and sent out for payment). The things we may want to check here should
    be pretty close to what we'll check when the item is added to the basket.

    Args:
    basket_id (int): the ID of the basket to process
    """


@hookspec
def post_sale(order_id, source):
    """
    Trigger post-sale events.

    This happens when the order has been completed, either via the browser
    redirect or via the back-office webhook. The caller should specify the
    source from the POST_SALE_SOURCES list (in unified_ecommerce.constants).

    Args:
    order_id (int): ID of the order that has been completed.
    source (str): Source of the order that has been completed; one of POST_SALE_SOURCES.
    """


@hookspec
def post_refund(order_id, source):
    """
    Trigger post-refund events.

    This happens when the order has been refunded. These generally should just
    come back from the back-office webhook but the source option is specified
    in case that changes.

    Args:
    order_id (int): ID of the order that has been completed.
    source (str): Source of the order that has been completed; one of POST_SALE_SOURCES.
    """
