"""Hookspecs for refunds."""
# ruff: noqa: ARG001

import pluggy

hookspec = pluggy.HookspecMarker("unified_ecommerce")


@hookspec
def refund_created(refund_id):
    """
    Complete actions that need to be taken when a refund is created.

    Args:
    refund_id (int): ID of the refund request.
    """


@hookspec
def refund_issued(refund_id):
    """
    Complete actions that need to be taken when a refund is issued.

    This should handle:
    - Marking the order as refunded.
    - Notifiying the integrated system of the order status, so it can take whatever
      steps are necessary.
    - Sending status emails.

    Args:
    refund_id (int): ID of the completed refund request.
    """
