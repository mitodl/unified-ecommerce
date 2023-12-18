"""View tests for system metadata."""

import pytest

from system_meta.factories import (
    ActiveProductFactory,
    InactiveProductFactory,
    IntegratedSystemFactory,
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
    factory_class = ActiveProductFactory
    queryset = Product.objects.all()

    list_url = "/api/meta/v0/product/"
    object_url = "/api/meta/v0/product/{}/"

    @pytest.mark.parametrize("isLoggedIn", [True, False])
    @pytest.mark.parametrize("isActiveProduct", [True, False])
    def test_retrieve(self, isLoggedIn, isActiveProduct, client, user_client):
        """
        Test that the viewset can retrieve an object that is either active or possibly
        inactive.
        """

        self.factory_class = (
            ActiveProductFactory if isActiveProduct else InactiveProductFactory
        )

        super().test_retrieve(isLoggedIn, client, user_client)

    @pytest.mark.parametrize("isActiveProduct", [True, False])
    @pytest.mark.parametrize("isLoggedIn", [True, False])
    def test_update(self, isActiveProduct, isLoggedIn, client, user_client):
        """Test that the viewset can update an object."""
        self.factory_class = (
            ActiveProductFactory if isActiveProduct else InactiveProductFactory
        )
        update_data = {"name": "Updated Name"}

        (instance, response) = super().test_update(
            update_data, isLoggedIn, client, user_client
        )

        if isLoggedIn:
            if not isActiveProduct:
                assert instance.name != update_data["name"]
                assert response.status_code == 404
                return

            instance.refresh_from_db()
            assert instance.name == update_data["name"]
        else:
            assert instance.name != update_data["name"]

    @pytest.mark.parametrize("isLoggedIn", [True, False])
    def test_delete(self, isLoggedIn, client, user_client):
        """Test that the viewset can delete an object."""
        (instance, response) = super().test_delete(isLoggedIn, client, user_client)

        if isLoggedIn:
            instance.refresh_from_db()
            assert response.status_code == 204
            assert instance.is_active is False
        else:
            assert instance.is_active is True

    @pytest.mark.parametrize("isLoggedIn", [True, False])
    @pytest.mark.parametrize("withBadData", [True, False])
    def test_create(self, withBadData, isLoggedIn, client, user_client):
        """Test that the viewset can create an object."""
        system = IntegratedSystemFactory.create()
        create_data = {
            "name": "New Name",
            "price": 10.00,
            "sku": "1234567890123",
            "system": system.id,
            "is_active": True,
        }

        if not withBadData:
            create_data["description"] = "a description"

        response = super().test_create(create_data, isLoggedIn, client, user_client)

        if isLoggedIn:
            assert response.status_code == 201 if not withBadData else 400
            assert Product.objects.filter(name="New Name").exists() is not withBadData
