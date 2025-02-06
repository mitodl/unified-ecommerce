"""Test factories for refunds."""

import faker
from factory import SubFactory, fuzzy, LazyAttribute, lazy_attribute
from factory.django import DjangoModelFactory

from payments.factories import LineFactory, OrderFactory
from refunds import models

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


class RequestRecipentFactory(DjangoModelFactory):
    """Factory for RequestRecipient"""

    class Meta:
        """Meta options for RequestRecipientFactory"""

        model = models.RequestRecipient
