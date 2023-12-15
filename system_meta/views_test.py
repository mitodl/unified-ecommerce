"""View tests for system metadata."""

import pytest

from system_meta.factories import IntegratedSystemFactory, ProductFactory
from system_meta.views import IntegratedSystemViewSet, ProductViewSet
from unified_ecommerce.test_utils import BaseViewSetTest

pytestmark = pytest.mark.django_db


class TestIntegratedSystemViewSet(BaseViewSetTest):
    """Tests for the IntegratedSystemViewSet."""

    viewset_class = IntegratedSystemViewSet
    factory_class = IntegratedSystemFactory


class TestProductViewSet(BaseViewSetTest):
    """Tests for the ProductViewSet."""

    viewset_class = ProductViewSet
    factory_class = ProductFactory
