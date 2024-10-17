"""Test factories for payments"""

import faker
from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory

from payments import models
from system_meta.factories import IntegratedSystemFactory, ProductFactory
from unified_ecommerce.factories import UserFactory

FAKE = faker.Factory.create()


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
