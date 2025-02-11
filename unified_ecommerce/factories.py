"""
Factory for Users
"""

import ulid
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from factory import Faker, LazyFunction, RelatedFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for Users"""

    global_id = Faker("uuid4")
    username = LazyFunction(lambda: ulid.new().str)
    email = FuzzyText(suffix="@example.com")
    first_name = FuzzyText()
    last_name = FuzzyText()
    is_active = True

    profile = RelatedFactory("users.factories.UserProfileFactory", "user")

    class Meta:
        """Meta options for UserFactory"""

        model = User
        skip_postgeneration_save = True


class GroupFactory(DjangoModelFactory):
    """Factory for Groups"""

    name = FuzzyText()

    class Meta:
        """Meta options for GroupFactory"""

        model = Group


class InactiveDjangoModelFactory(DjangoModelFactory):
    """Meta factory for deleted objects."""

    class Meta:
        """Meta options for InactiveDjangoModelFactory."""

        abstract = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Create the object, but then delete it."""
        obj = super()._create(model_class, *args, **kwargs)
        obj.delete()
        return obj
