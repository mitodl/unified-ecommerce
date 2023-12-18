"""View tests for system metadata."""

import pytest

from system_meta.factories import (
    ActiveProductFactory,
    IntegratedSystemFactory,
    ProductFactory,
)
from system_meta.models import IntegratedSystem, Product
from system_meta.views import IntegratedSystemViewSet, ProductViewSet
from unified_ecommerce.test_utils import BaseViewSetTest

pytestmark = pytest.mark.django_db


class TestIntegratedSystemViewSet(BaseViewSetTest):
    """Tests for the IntegratedSystemViewSet."""

    viewset_class = IntegratedSystemViewSet
    factory_class = IntegratedSystemFactory
    queryset = IntegratedSystem.objects.all()

    list_url = "/api/meta/v0/integrated_system/"
    detail_url = "/api/meta/v0/integrated_system/{}/"


class TestProductViewSet(BaseViewSetTest):
    """Tests for the ProductViewSet."""

    viewset_class = ProductViewSet
    factory_class = ProductFactory
    queryset = Product.objects.all()

    list_url = "/api/meta/v0/product/"
    detail_url = "/api/meta/v0/product/{}/"

    @pytest.mark.parametrize("isLoggedIn", [True, False])
    @pytest.mark.parametrize("isActiveProduct", [True, False])
    def test_retrieve(self, isLoggedIn, isActiveProduct, client, user_client):
        """
        Test that the viewset can retrieve an object that is either active or possibly
        inactive.
        """

        self.factory_class = ActiveProductFactory if isActiveProduct else ProductFactory

        super().test_retrieve(isLoggedIn, client, user_client)
