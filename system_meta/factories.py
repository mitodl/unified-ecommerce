"""Factories for the system_meta app."""

import faker
import reversion
from factory import Faker, LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from reversion.models import Version

from system_meta.models import IntegratedSystem, Product
from unified_ecommerce.factories import InactiveDjangoModelFactory

FAKE = faker.Faker()


class IntegratedSystemFactory(DjangoModelFactory):
    """Factory for IntegratedSystem model."""

    class Meta:
        """Meta options for IntegratedSystemFactory."""

        model = IntegratedSystem

    name = LazyAttribute(lambda obj: FAKE.unique.company())  # noqa: ARG005
    description = FAKE.text()
    api_key = FAKE.md5()
    webhook_url = FAKE.url()


class ActiveIntegratedSystemFactory(IntegratedSystemFactory):
    """Factory for IntegratedSystem model, but always returns an active object."""


class InactiveIntegratedSystemFactory(
    IntegratedSystemFactory, InactiveDjangoModelFactory
):
    """Factory for IntegratedSystem model, but always returns an inactive object."""


class ProductFactory(DjangoModelFactory):
    """Factory for Product model."""

    class Meta:
        """Meta options for ProductFactory."""

        model = Product

    name = Faker("word")
    price = Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    sku = Faker("ean", length=13)
    description = Faker("text")
    system = SubFactory(IntegratedSystemFactory)
    system_data = Faker("json")
    image_metadata = {
        "image_url": "http://example.com/image.jpg",
        "alt_text": "Image alt text",
        "description": "Image description",
    }
    details_url = Faker("url")


class ActiveProductFactory(ProductFactory):
    """Factory for Product model, but always returns an active product."""


class InactiveProductFactory(ProductFactory, InactiveDjangoModelFactory):
    """Factory for Product model, but always returns an inactive product."""


class ProductVersionFactory:
    """Factory for ProductVersion"""

    @staticmethod
    def create(**kwargs):
        """
        Create a single ProductVersion.

        This uses the ProductFactory so you should be able to specify defaults
        as normal.
        """

        with reversion.create_revision():
            product = ProductFactory.create(**kwargs)

        return Version.objects.get_for_object(product).first()

    @staticmethod
    def create_batch(number, **kwargs):
        """Create several ProductVersions. Same as ProductVersion, just more."""

        return [ProductVersionFactory.create(**kwargs) for _ in range(number)]
