"""Test factories for payments"""

import faker
from factory import SubFactory, fuzzy, lazy_attribute
from factory.django import DjangoModelFactory

from payments import models
from system_meta.factories import IntegratedSystemFactory, ProductFactory
from unified_ecommerce.constants import TRANSACTION_TYPE_PAYMENT
from unified_ecommerce.factories import UserFactory
from unified_ecommerce.utils import now_in_utc

FAKE = faker.Faker()


class BasketFactory(DjangoModelFactory):
    """Factory for Basket"""

    user = SubFactory(UserFactory)
    integrated_system = SubFactory(IntegratedSystemFactory)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Basket


class BasketItemFactory(DjangoModelFactory):
    """Factory for BasketItem"""

    product = SubFactory(ProductFactory)
    basket = SubFactory(BasketFactory)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.BasketItem


class OrderFactory(DjangoModelFactory):
    """Factory for Order"""

    total_price_paid = fuzzy.FuzzyDecimal(10.00, 10.00)
    purchaser = SubFactory(UserFactory)
    reference_number = FAKE.unique.word()
    integrated_system = SubFactory(IntegratedSystemFactory)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Order


class TransactionFactory(DjangoModelFactory):
    """Factory for Transaction"""

    transaction_id = FAKE.uuid4()
    order = SubFactory(OrderFactory)
    amount = fuzzy.FuzzyDecimal(10.00, 10.00)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Transaction


class PaymentTransactionFactory(TransactionFactory):
    """Transaction factory, but returns a payment-type transaction."""

    transaction_type = TRANSACTION_TYPE_PAYMENT

    @lazy_attribute
    def data(self):
        """
        Generate some faked data for the transaction that generally matches CyberSource.
        """

        faked_transaction_data = {
            "utf8": "✓",
            "message": "Request was processed successfully.",
            "decision": "ACCEPT",
            "auth_code": "888888",
            "auth_time": now_in_utc().isoformat(),
            "signature": "".join(FAKE.random_letters(32)),
            "req_amount": float(self.order.total_price_paid),
            "req_locale": "en-us",
            "auth_amount": float(self.order.total_price_paid),
            "reason_code": "100",
            "req_currency": "USD",
            "auth_avs_code": "1",
            "auth_response": "100",
            "req_card_type": "001",
            "request_token": str("".join(FAKE.random_letters(32))),
            "auth_cv_result": "M",
            "card_type_name": "Visa",
            "req_access_key": str("".join(FAKE.random_letters(32))),
            "req_profile_id": FAKE.uuid4(),
            "transaction_id": FAKE.random_number(22),
            "req_card_number": "xxxxxxxxxxxx1111",
            "req_consumer_id": FAKE.random_number(22),
            "signed_date_time": now_in_utc().isoformat(),
            "auth_trans_ref_no": str("".join(FAKE.random_letters(16))),
            "bill_trans_ref_no": str("".join(FAKE.random_letters(16))),
            "req_bill_to_email": FAKE.email(),
            "auth_cv_result_raw": "M",
            "req_payment_method": "card",
            "signed_field_names": "",
            "req_bill_to_surname": FAKE.last_name(),
            "req_bill_to_forename": FAKE.first_name(),
            "req_card_expiry_date": FAKE.future_date().strftime("%m-%y"),
            "req_transaction_type": "sale",
            "req_transaction_uuid": FAKE.random_number(22),
            "req_customer_ip_address": FAKE.ipv4(),
            "req_bill_to_address_city": "p",
            "req_bill_to_address_line1": "p",
            "req_bill_to_address_line2": "p",
            "req_bill_to_address_state": "p",
            "req_merchant_defined_data1": "490",
            "req_bill_to_address_country": "PK",
            "req_bill_to_address_postal_code": "p",
            "req_override_custom_cancel_page": FAKE.url(),
            "req_override_custom_receipt_page": FAKE.url(),
            "req_card_type_selection_indicator": "1",
            "req_reference_number": self.order.reference_number,
            "req_line_item_count": len(self.order.lines.all()),
        }

        for idx, line in enumerate(self.order.lines.all()):
            faked_transaction_data[f"req_item_{idx}_code"] = line.product.id
            faked_transaction_data[f"req_item_{idx}_name"] = line.product.name
            faked_transaction_data[f"req_item_{idx}_quantity"] = line.quantity
            faked_transaction_data[f"req_item_{idx}_sku"] = line.product.sku
            faked_transaction_data[f"req_item_{idx}_tax_amount"] = float(line.tax)
            faked_transaction_data[f"req_item_{idx}_unit_price"] = float(
                line.unit_price
            )

        return faked_transaction_data


class PaypalPaymentTransactionFactory(TransactionFactory):
    """Factory for a payment transaction, but adds PayPal-specific fields."""

    @lazy_attribute
    def data(self):
        """Create fake transaction data that includes PayPal signifiers."""

        # We only check for this right now. If we get to a point where we can actually
        # process PayPal transactions, we'll need to update this so we can test
        # that fully.
        return {
            "paypal_token": FAKE.uuid4(),
        }


class LineFactory(DjangoModelFactory):
    """Factory for Line"""

    quantity = 1
    order = SubFactory(OrderFactory)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Line


class BlockedCountryFactory(DjangoModelFactory):
    """Factory for BlockedCountry"""

    country_code = FAKE.country_code(representation="alpha-2")

    class Meta:
        """Meta options for BlockedCountryFactory"""

        model = models.BlockedCountry


class TaxRateFactory(DjangoModelFactory):
    """Factory for TaxRate"""

    country_code = FAKE.country_code(representation="alpha-2")
    tax_rate = fuzzy.FuzzyDecimal(low=0, high=99, precision=4)

    class Meta:
        """Meta options for BlockedCountryFactory"""

        model = models.TaxRate


class DiscountFactory(DjangoModelFactory):
    """Factory for Discount"""

    amount = fuzzy.FuzzyDecimal(low=0, high=99, precision=4)
    payment_type = fuzzy.FuzzyChoice(
        [
            "marketing",
            "sales",
            "financial-assistance",
            "customer-support",
            "staff",
        ]
    )
    discount_type = fuzzy.FuzzyChoice(["dollars-off", "percent-off", "fixed-price"])
    discount_code = FAKE.word()

    class Meta:
        """Meta options for DiscountFactory"""

        model = models.Discount


class CompanyFactory(DjangoModelFactory):
    """Factory for Company"""

    name = FAKE.unique.company()

    class Meta:
        """Meta options for CompanyFactory"""

        model = models.Company


class BulkDiscountCollectionFactory(DjangoModelFactory):
    """Factory for BulkDiscountCollection"""

    prefix = FAKE.unique.word()

    class Meta:
        """Meta options for BulkDiscountCollectionFactory"""

        model = models.BulkDiscountCollection


class RedeemedDiscountFactory(DjangoModelFactory):
    """Factory for RedeemedDiscount"""

    discount = SubFactory(DiscountFactory)
    order = SubFactory(OrderFactory)
    user = SubFactory(UserFactory)

    class Meta:
        """Meta options for RedeemedDiscountFactory"""

        model = models.RedeemedDiscount
