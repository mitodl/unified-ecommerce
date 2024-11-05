"""Factories for users."""

import faker
from factory import SubFactory
from factory.django import DjangoModelFactory

from users.models import UserProfile

FAKE = faker.Faker()


class UserProfileFactory(DjangoModelFactory):
    """Factory for UserProfile."""

    country_code = FAKE.country_code()
    user = SubFactory("unified_ecommerce.factories.UserFactory")

    class Meta:
        """Meta options for the factory"""

        model = UserProfile
