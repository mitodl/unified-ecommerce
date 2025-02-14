"""Test factories for payments"""

import faker
from factory import SubFactory, fuzzy, RelatedFactoryList
from factory.django import DjangoModelFactory

from payments import models
from system_meta.factories import IntegratedSystemFactory, ProductFactory
from unified_ecommerce.factories import UserFactory

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

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Order


class TransactionFactory(DjangoModelFactory):
    """Factory for Transaction"""

    order = SubFactory(OrderFactory)
    amount = fuzzy.FuzzyDecimal(10.00, 10.00)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Transaction


class LineFactory(DjangoModelFactory):
    """Factory for Line"""

    quantity = 1
    order = SubFactory(OrderFactory)

    class Meta:
        """Meta options for BasketFactory"""

        model = models.Line


class BlockedCountryFactory(DjangoModelFactory):
    """Factory for BlockedCountry"""

    country_code = FAKE.unique.country_code(representation="alpha-2")

    class Meta:
        """Meta options for BlockedCountryFactory"""

        model = models.BlockedCountry


class TaxRateFactory(DjangoModelFactory):
    """Factory for TaxRate"""

    country_code = FAKE.unique.country_code(representation="alpha-2")
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
    discount_code = FAKE.unique.word()
    integrated_system = SubFactory(IntegratedSystemFactory)
    product = SubFactory(ProductFactory)

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
