"""Test factories for refunds."""

import faker
from factory import LazyAttribute, SubFactory
from factory.django import DjangoModelFactory

from payments.factories import OrderFactory
from refunds import models
from system_meta.factories import IntegratedSystemFactory

FAKE = faker.Faker()


class RequestLineFactory(DjangoModelFactory):
    """Factory for RequestLine"""

    class Meta:
        """Meta options for RequestLineFactory"""

        model = models.RequestLine


class RequestFactory(DjangoModelFactory):
    """Factory for Request"""

    order = SubFactory(OrderFactory)
    requester = LazyAttribute(lambda o: o.order.purchaser)

    class Meta:
        """Meta options for RequestFactory"""

        model = models.Request


class RequestRecipientFactory(DjangoModelFactory):
    """Factory for RequestRecipient"""

    email = FAKE.unique.email()
    integrated_system = SubFactory(IntegratedSystemFactory)

    class Meta:
        """Meta options for RequestRecipientFactory"""

        model = models.RequestRecipient
