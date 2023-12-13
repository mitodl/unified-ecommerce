"""
Factory for Users
"""

import ulid
from django.contrib.auth.models import Group, User
from factory import LazyFunction, RelatedFactory, Trait
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText


class UserFactory(DjangoModelFactory):
    """Factory for Users"""

    username = LazyFunction(lambda: ulid.new().str)
    email = FuzzyText(suffix="@example.com")
    first_name = FuzzyText()
    last_name = FuzzyText()

    profile = RelatedFactory("profiles.factories.ProfileFactory", "user")

    class Meta:
        """Meta options for UserFactory"""

        model = User
        skip_postgeneration_save = True

    class Params:
        """Params for UserFactory"""

        no_profile = Trait(profile=None)


class GroupFactory(DjangoModelFactory):
    """Factory for Groups"""

    name = FuzzyText()

    class Meta:
        """Meta options for GroupFactory"""

        model = Group
