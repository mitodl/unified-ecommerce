"""Factories for the system_meta app."""
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from system_meta.models import IntegratedSystem, Product


class IntegratedSystemFactory(DjangoModelFactory):
    """Factory for IntegratedSystem model."""

    class Meta:
        """Meta options for IntegratedSystemFactory."""

        model = IntegratedSystem

    name = Faker("company")
    description = Faker("text")
    api_key = Faker("md5")


class ProductFactory(DjangoModelFactory):
    """Factory for Product model."""

    class Meta:
        """Meta options for ProductFactory."""

        model = Product

    name = Faker("word")
    price = Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    sku = Faker("ean", length=13)
    description = Faker("text")
    is_active = Faker("boolean")
    system = SubFactory(IntegratedSystemFactory)
    system_data = Faker("json")
