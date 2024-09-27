"""Hookspecs for the payments app."""
# ruff: noqa: ARG001

import pluggy

hookspec = pluggy.HookspecMarker("unified_ecommerce")


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
