"""Constants for ecommerce."""
# ruff: noqa: ERA001

from mitol.payment_gateway.api import ProcessorResponse

# Application constants

USER_MSG_COOKIE_NAME = "user-message"
# Max age value = number of seconds
USER_MSG_COOKIE_MAX_AGE = 20
USER_MSG_TYPE_ENROLLED = "enrolled"
USER_MSG_TYPE_ENROLL_FAILED = "enroll-failed"
USER_MSG_TYPE_ENROLL_BLOCKED = "enroll-blocked"
USER_MSG_TYPE_ENROLL_DUPLICATED = "enroll-duplicated"
USER_MSG_TYPE_COMPLETED_AUTH = "completed-auth"
USER_MSG_TYPE_COURSE_NON_UPGRADABLE = "course-non-upgradable"
USER_MSG_TYPE_DISCOUNT_INVALID = "discount-invalid"

USER_MSG_TYPE_PAYMENT_DECLINED = "payment-declined"
USER_MSG_TYPE_PAYMENT_ERROR = "payment-error"
USER_MSG_TYPE_PAYMENT_CANCELLED = "payment-cancelled"
USER_MSG_TYPE_PAYMENT_REVIEW = "payment-review"
USER_MSG_TYPE_PAYMENT_ACCEPTED = "payment-accepted"
USER_MSG_TYPE_PAYMENT_ACCEPTED_NOVALUE = "payment-accepted-no-value"
USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN = "payment-error-unknown"

DISALLOWED_CURRENCY_CUBAN_PESO = "CUP"
DISALLOWED_CURRENCY_CUBAN_PESO_CONVERTED = "CUC"
DISALLOWED_CURRENCY_IRANIAN_RIAL = "IRR"
DISALLOWED_CURRENCY_SYRIAN_POUND = "SYP"
DISALLOWED_CURRENCY_NORTH_KOREAN_WON = "KPW"

DISALLOWED_CURRENCY_TYPES = [
    DISALLOWED_CURRENCY_CUBAN_PESO,
    DISALLOWED_CURRENCY_CUBAN_PESO_CONVERTED,
    DISALLOWED_CURRENCY_IRANIAN_RIAL,
    DISALLOWED_CURRENCY_SYRIAN_POUND,
    DISALLOWED_CURRENCY_NORTH_KOREAN_WON,
]

# Flagged countries constants

FLAGGED_COUNTRY_TAX = "tax"
FLAGGED_COUNTRY_BLOCKED = "blocked"
FLAGGED_COUNTRY_TYPES = [
    FLAGGED_COUNTRY_TAX,
    FLAGGED_COUNTRY_BLOCKED,
]

# Discount constants

DISCOUNT_TYPE_PERCENT_OFF = "percent-off"
DISCOUNT_TYPE_DOLLARS_OFF = "dollars-off"
DISCOUNT_TYPE_FIXED_PRICE = "fixed-price"

ALL_DISCOUNT_TYPES = [
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
]
DISCOUNT_TYPES = list(zip(ALL_DISCOUNT_TYPES, ALL_DISCOUNT_TYPES))

REDEMPTION_TYPE_ONE_TIME = "one-time"
REDEMPTION_TYPE_ONE_TIME_PER_USER = "one-time-per-user"
REDEMPTION_TYPE_UNLIMITED = "unlimited"

ALL_REDEMPTION_TYPES = [
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
]

REDEMPTION_TYPES = list(zip(ALL_REDEMPTION_TYPES, ALL_REDEMPTION_TYPES))

PAYMENT_TYPE_MARKETING = "marketing"
PAYMENT_TYPE_SALES = "sales"
PAYMENT_TYPE_FINANCIAL_ASSISTANCE = "financial-assistance"
PAYMENT_TYPE_CUSTOMER_SUPPORT = "customer-support"
PAYMENT_TYPE_STAFF = "staff"
PAYMENT_TYPE_LEGACY = "legacy"
PAYMENT_TYPE_CC = "credit_card"
PAYMENT_TYPE_PO = "purchase_order"

ALL_PAYMENT_TYPES = [
    PAYMENT_TYPE_MARKETING,
    PAYMENT_TYPE_SALES,
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    PAYMENT_TYPE_CUSTOMER_SUPPORT,
    PAYMENT_TYPE_STAFF,
    PAYMENT_TYPE_LEGACY,
    PAYMENT_TYPE_CC,
    PAYMENT_TYPE_PO,
]

PAYMENT_TYPES = list(zip(ALL_PAYMENT_TYPES, ALL_PAYMENT_TYPES))

# Transaction constants

TRANSACTION_TYPE_REFUND = "refund"
TRANSACTION_TYPE_PAYMENT = "payment"

ALL_TRANSACTION_TYPES = [TRANSACTION_TYPE_PAYMENT, TRANSACTION_TYPE_REFUND]

TRANSACTION_TYPES = list(zip(ALL_TRANSACTION_TYPES, ALL_TRANSACTION_TYPES))

CYBERSOURCE_CARD_TYPES = {
    "001": "Visa",
    "002": "Mastercard",
    "003": "American Express",
    "004": "Discover",
    "005": "Diners Club",
    "006": "Carte Blanche",
    "007": "JCB",
    "014": "Enroute",
    "021": "JAL",
    "024": "Maestro (UK)",
    "031": "Delta",
    "033": "Visa Electron",
    "034": "Dankort",
    "036": "Carte Bancaires",
    "037": "Carta Si",
    "039": "EAN",
    "040": "UATP",
    "042": "Maestro (Intl)",
    "050": "Hipercard",
    "051": "Aura",
    "054": "Elo",
    "061": "RuPay",
    "062": "China UnionPay",
}

REFUND_SUCCESS_STATES = [
    ProcessorResponse.STATE_ACCEPTED,
    ProcessorResponse.STATE_PENDING,
]

ZERO_PAYMENT_DATA = {"amount": 0, "data": {"reason": "No payment required"}}

CYBERSOURCE_REASON_CODE_SUCCESS = 100
CYBERSOURCE_REASON_CODE_MISSING_FIELDS = 101
CYBERSOURCE_REASON_CODE_INVALID_DATA = 102
CYBERSOURCE_REASON_CODE_DUPLICATE_TRANSACTION = 104
CYBERSOURCE_REASON_CODE_PARTIAL_APPROVE = 110
CYBERSOURCE_REASON_CODE_SYSTEM_FAILURE = 150
CYBERSOURCE_REASON_CODE_SERVER_TIMEOUT = 151
CYBERSOURCE_REASON_CODE_SERVICE_TIMEOUT = 152
CYBERSOURCE_REASON_CODE_DECLINE_AVS_FAIL = 200
CYBERSOURCE_REASON_CODE_DECLINE_VERBAL_AUTH = 201
CYBERSOURCE_REASON_CODE_DECLINE_EXPIRED_CARD = 202
CYBERSOURCE_REASON_CODE_DECLINE_DECLINED = 203
CYBERSOURCE_REASON_CODE_DECLINE_NSF = 204
CYBERSOURCE_REASON_CODE_DECLINE_CARD_STOLEN_LOST = 205
CYBERSOURCE_REASON_CODE_DECLINE_ISSUING_UNAVAILALBE = 207
CYBERSOURCE_REASON_CODE_DECLINE_CARD_INACTIVE = 208
CYBERSOURCE_REASON_CODE_DECLINE_CARD_LIMIT = 210
CYBERSOURCE_REASON_CODE_DECLINE_CVN_INVALID = 211
CYBERSOURCE_REASON_CODE_DECLINE_NEGATIVE_FILE = 221
CYBERSOURCE_REASON_CODE_DECLINE_ACCOUNT_FROZEN = 222
CYBERSOURCE_REASON_CODE_DECLINE_CVN_FAILED = 230
CYBERSOURCE_REASON_CODE_DECLINE_INVALID_ACCOUNT = 231
CYBERSOURCE_REASON_CODE_DECLINE_CARD_TYPE_INVALID = 232
CYBERSOURCE_REASON_CODE_DECLINE_GENERAL_DECLINE = 233
CYBERSOURCE_REASON_CODE_DECLINE_ACCOUNT_INFORMATION_INCORRECT = 234
CYBERSOURCE_REASON_CODE_DECLINE_PROCESSOR_FAILURE = 236
CYBERSOURCE_REASON_CODE_DECLINE_CARD_TYPE_MISMATCH = 240
CYBERSOURCE_REASON_CODE_PAYER_AUTHENTICATION = 475
CYBERSOURCE_REASON_CODE_PAYER_AUTHENTICATION_FAILED = 476
CYBERSOURCE_REASON_CODE_PAYER_AUTHENTICATION_SCA_REQUIRED = 478
CYBERSOURCE_REASON_CODE_DECLINE_PROFILE_SETTINGS = 481
CYBERSOURCE_REASON_CODE_DECLINE_DECISION_MANAGER = 520

CYBERSOURCE_ACCEPT_CODES = [
    CYBERSOURCE_REASON_CODE_SUCCESS,
    CYBERSOURCE_REASON_CODE_PARTIAL_APPROVE,
]

CYBERSOURCE_REVIEW_CODES = [
    CYBERSOURCE_REASON_CODE_DECLINE_AVS_FAIL,
    CYBERSOURCE_REASON_CODE_DECLINE_VERBAL_AUTH,
    CYBERSOURCE_REASON_CODE_DECLINE_CVN_FAILED,
    CYBERSOURCE_REASON_CODE_DECLINE_DECISION_MANAGER,
]

CYBERSOURCE_DECLINE_CODES = [
    CYBERSOURCE_REASON_CODE_INVALID_DATA,
    CYBERSOURCE_REASON_CODE_DECLINE_AVS_FAIL,
    CYBERSOURCE_REASON_CODE_DECLINE_EXPIRED_CARD,
    CYBERSOURCE_REASON_CODE_DECLINE_DECLINED,
    CYBERSOURCE_REASON_CODE_DECLINE_NSF,
    CYBERSOURCE_REASON_CODE_DECLINE_CARD_STOLEN_LOST,
    CYBERSOURCE_REASON_CODE_DECLINE_ISSUING_UNAVAILALBE,
    CYBERSOURCE_REASON_CODE_DECLINE_CARD_INACTIVE,
    CYBERSOURCE_REASON_CODE_DECLINE_CARD_LIMIT,
    CYBERSOURCE_REASON_CODE_DECLINE_CVN_INVALID,
    CYBERSOURCE_REASON_CODE_DECLINE_NEGATIVE_FILE,
    CYBERSOURCE_REASON_CODE_DECLINE_ACCOUNT_FROZEN,
    CYBERSOURCE_REASON_CODE_DECLINE_CVN_FAILED,
    CYBERSOURCE_REASON_CODE_DECLINE_INVALID_ACCOUNT,
    CYBERSOURCE_REASON_CODE_DECLINE_CARD_TYPE_INVALID,
    CYBERSOURCE_REASON_CODE_DECLINE_GENERAL_DECLINE,
    CYBERSOURCE_REASON_CODE_DECLINE_ACCOUNT_INFORMATION_INCORRECT,
    CYBERSOURCE_REASON_CODE_DECLINE_PROCESSOR_FAILURE,
    CYBERSOURCE_REASON_CODE_DECLINE_CARD_TYPE_MISMATCH,
    CYBERSOURCE_REASON_CODE_PAYER_AUTHENTICATION,
    CYBERSOURCE_REASON_CODE_PAYER_AUTHENTICATION_FAILED,
    CYBERSOURCE_REASON_CODE_PAYER_AUTHENTICATION_SCA_REQUIRED,
    CYBERSOURCE_REASON_CODE_DECLINE_PROFILE_SETTINGS,
]

CYBERSOURCE_ERROR_CODES = [
    CYBERSOURCE_REASON_CODE_INVALID_DATA,
    CYBERSOURCE_REASON_CODE_DUPLICATE_TRANSACTION,
    CYBERSOURCE_REASON_CODE_SYSTEM_FAILURE,
    CYBERSOURCE_REASON_CODE_SERVER_TIMEOUT,
    CYBERSOURCE_REASON_CODE_SERVICE_TIMEOUT,
]

# Post-sale hook sources

POST_SALE_SOURCE_REDIRECT = "redirect"
POST_SALE_SOURCE_BACKOFFICE = "backoffice"

POST_SALE_SOURCES = [
    POST_SALE_SOURCE_REDIRECT,
    POST_SALE_SOURCE_BACKOFFICE,
]

# Refund hook sources

REFUND_SOURCE_REDIRECT = "redirect"
REFUND_SOURCE_BACKOFFICE = "backoffice"

REFUND_SOURCES = [
    REFUND_SOURCE_REDIRECT,
    REFUND_SOURCE_BACKOFFICE,
]

# Refund statuses

REFUND_STATUS_PENDING = "pending"
REFUND_STATUS_CREATED = "created"
REFUND_STATUS_DENIED = "denied"
REFUND_STATUS_APPROVED = "approved"
REFUND_STATUS_FAILED = "failed"

REFUND_STATUSES = [
    REFUND_STATUS_PENDING,
    REFUND_STATUS_CREATED,
    REFUND_STATUS_DENIED,
    REFUND_STATUS_APPROVED,
    REFUND_STATUS_FAILED,
]
REFUND_STATUS_CHOICES = list(zip(REFUND_STATUSES, REFUND_STATUSES))

REFUND_CODE_TYPE_APPROVE = "approve"
REFUND_CODE_TYPE_DENY = "deny"
REFUND_CODE_TYPES = [
    REFUND_CODE_TYPE_APPROVE,
    REFUND_CODE_TYPE_DENY,
]
REFUND_CODE_TYPE_CHOICES = list(zip(REFUND_CODE_TYPES, REFUND_CODE_TYPES))
