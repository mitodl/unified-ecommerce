"""
Constants for the payments app.
"""

PAYMENT_HOOK_ACTION_PRE_SALE = "presale"
PAYMENT_HOOK_ACTION_POST_SALE = "postsale"
PAYMENT_HOOK_ACTION_POST_REFUND = "postrefund"

PAYMENT_HOOK_ACTIONS = zip(
    [
        PAYMENT_HOOK_ACTION_PRE_SALE,
        PAYMENT_HOOK_ACTION_POST_SALE,
        PAYMENT_HOOK_ACTION_POST_REFUND,
    ],
    [
        PAYMENT_HOOK_ACTION_PRE_SALE,
        PAYMENT_HOOK_ACTION_POST_SALE,
        PAYMENT_HOOK_ACTION_POST_REFUND,
    ],
)
