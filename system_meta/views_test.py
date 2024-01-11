"""View tests for system metadata."""

import pytest

from system_meta.factories import (
    ActiveIntegratedSystemFactory,
    ActiveProductFactory,
    InactiveIntegratedSystemFactory,
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
    factory_class = ActiveIntegratedSystemFactory
    queryset = IntegratedSystem.objects.all()

    list_url = "/api/v0/meta/integrated_system/"
    object_url = "/api/v0/meta/integrated_system/{}/"

    @pytest.mark.parametrize("is_logged_in", [True, False])
    @pytest.mark.parametrize("is_active_system", [True, False])
    def test_retrieve(self, is_logged_in, is_active_system, client, user_client):
        """
        Test that the viewset can retrieve an object that is either active or possibly
        inactive.
        """

        self.factory_class = (
            ActiveIntegratedSystemFactory
            if is_active_system
            else InactiveIntegratedSystemFactory
        )

        super().test_retrieve(is_logged_in, client, user_client)

    @pytest.mark.parametrize("is_active_system", [True, False])
    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_update(self, is_active_system, is_logged_in, client, user_client):
        """Test that the viewset can update an object."""
        self.factory_class = (
            ActiveIntegratedSystemFactory
            if is_active_system
            else InactiveIntegratedSystemFactory
        )
        update_data = {"name": "Updated Name"}

        (instance, response) = super().test_update(
            update_data, is_logged_in, client, user_client
        )

        if is_logged_in:
            if not is_active_system:
                assert instance.name != update_data["name"]
                assert response.status_code == 404
                return

            instance.refresh_from_db()
            assert instance.name == update_data["name"]
        else:
            assert instance.name != update_data["name"]

    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_delete(self, is_logged_in, client, user_client):
        """Test that the viewset can delete an object."""
        (instance, response) = super().test_delete(is_logged_in, client, user_client)

        if is_logged_in:
            instance.refresh_from_db()
            assert response.status_code == 204
            assert instance.is_active is not None
        else:
            assert instance.is_active is None

    @pytest.mark.parametrize("is_logged_in", [True, False])
    @pytest.mark.parametrize("with_bad_data", [True, False])
    def test_create(self, with_bad_data, is_logged_in, client, user_client):
        """Test that the viewset can create an object."""
        create_data = {
            "description": "a description",
            "is_active": True,
            "api_key": "123456",
        }

        if not with_bad_data:
            create_data["name"] = "System Name"

        response = super().test_create(create_data, is_logged_in, client, user_client)

        if is_logged_in:
            assert response.status_code == 201 if not with_bad_data else 400
            assert (
                IntegratedSystem.objects.filter(name="System Name").exists()
                is not with_bad_data
            )
        else:
            assert response.data["detail"].code == "not_authenticated"
            assert response.status_code == 403


class TestProductViewSet(BaseViewSetTest):
    """Tests for the ProductViewSet."""

    viewset_class = ProductViewSet
    factory_class = ActiveProductFactory
    queryset = Product.objects.all()

    list_url = "/api/v0/meta/product/"
    object_url = "/api/v0/meta/product/{}/"

    @pytest.mark.parametrize("is_logged_in", [True, False])
    @pytest.mark.parametrize("is_active_product", [True, False])
    def test_retrieve(self, is_logged_in, is_active_product, client, user_client):
        """
        Test that the viewset can retrieve an object that is either active or possibly
        inactive.
        """

        self.factory_class = (
            ActiveProductFactory if is_active_product else InactiveProductFactory
        )

        super().test_retrieve(is_logged_in, client, user_client)

    @pytest.mark.parametrize("is_active_product", [True, False])
    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_update(self, is_active_product, is_logged_in, client, user_client):
        """Test that the viewset can update an object."""
        self.factory_class = (
            ActiveProductFactory if is_active_product else InactiveProductFactory
        )
        update_data = {"name": "Updated Name"}

        (instance, response) = super().test_update(
            update_data, is_logged_in, client, user_client
        )

        if is_logged_in:
            if not is_active_product:
                assert instance.name != update_data["name"]
                assert response.status_code == 404
                return

            instance.refresh_from_db()
            assert instance.name == update_data["name"]
        else:
            assert instance.name != update_data["name"]

    @pytest.mark.parametrize("is_logged_in", [True, False])
    def test_delete(self, is_logged_in, client, user_client):
        """Test that the viewset can delete an object."""
        (instance, response) = super().test_delete(is_logged_in, client, user_client)

        if is_logged_in:
            instance.refresh_from_db()
            assert response.status_code == 204
            assert instance.is_active is not None
        else:
            assert instance.is_active is None

    @pytest.mark.parametrize("is_logged_in", [True, False])
    @pytest.mark.parametrize("with_bad_data", [True, False])
    def test_create(self, with_bad_data, is_logged_in, client, user_client):
        """Test that the viewset can create an object."""
        system = IntegratedSystemFactory.create()
        create_data = {
            "name": "New Name",
            "price": 10.00,
            "sku": "1234567890123",
            "system": system.id,
            "is_active": True,
        }

        if not with_bad_data:
            create_data["description"] = "a description"

        response = super().test_create(create_data, is_logged_in, client, user_client)

        if is_logged_in:
            assert response.status_code == 201 if not with_bad_data else 400
            assert Product.objects.filter(name="New Name").exists() is not with_bad_data
        else:
            assert response.data["detail"].code == "not_authenticated"
            assert response.status_code == 403
