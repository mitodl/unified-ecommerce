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
from system_meta.serializers import (
    AdminIntegratedSystemSerializer,
    IntegratedSystemSerializer,
    ProductSerializer,
)
from system_meta.views import IntegratedSystemViewSet, ProductViewSet
from unified_ecommerce.test_utils import AuthVariegatedModelViewSetTest

pytestmark = pytest.mark.django_db


class TestIntegratedSystemViewSet(AuthVariegatedModelViewSetTest):
    """Tests for the IntegratedSystemViewSet."""

    viewset_class = IntegratedSystemViewSet
    factory_class = ActiveIntegratedSystemFactory
    queryset = IntegratedSystem.all_objects.all()

    list_url = "/api/v0/meta/integrated_system/"
    object_url = "/api/v0/meta/integrated_system/{}/"

    read_only_serializer_class = IntegratedSystemSerializer
    read_write_serializer_class = AdminIntegratedSystemSerializer

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user", "is_active_system"),
        [
            (True, False, True),
            (True, True, True),
            (False, False, True),
            (True, False, False),
            (True, True, False),
            (False, False, False),
        ],
    )
    def test_retrieve(  # noqa: PLR0913
        self,
        is_active_system,
        is_logged_in,
        use_staff_user,
        client,
        user_client,
        staff_client,
    ):
        """
        Test that the viewset can retrieve an object that is either active or possibly
        inactive.
        """

        self.factory_class = (
            ActiveIntegratedSystemFactory
            if is_active_system
            else InactiveIntegratedSystemFactory
        )

        super().test_retrieve(
            is_logged_in, use_staff_user, client, user_client, staff_client
        )

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user", "is_active_system"),
        [
            (True, False, True),
            (True, True, True),
            (False, False, True),
            (True, False, False),
            (True, True, False),
            (False, False, False),
        ],
    )
    def test_update(  # noqa: PLR0913
        self,
        is_active_system,
        is_logged_in,
        use_staff_user,
        client,
        user_client,
        staff_client,
    ):
        """Test that the viewset can update an object."""
        self.factory_class = (
            ActiveIntegratedSystemFactory
            if is_active_system
            else InactiveIntegratedSystemFactory
        )
        update_data = {"name": "Updated Name"}

        (instance, response) = super().test_update(
            update_data, is_logged_in, use_staff_user, client, user_client, staff_client
        )

        if is_logged_in and use_staff_user:
            if not is_active_system:
                assert instance.name != update_data["name"]
                assert response.status_code == 404
                return

            instance.refresh_from_db()
            assert instance.name == update_data["name"]
        else:
            assert instance.name != update_data["name"]

    @pytest.mark.parametrize(
        (
            "is_logged_in",
            "use_staff_user",
        ),
        [
            (
                True,
                False,
            ),
            (
                True,
                True,
            ),
            (
                False,
                False,
            ),
        ],
    )
    def test_delete(  # noqa: PLR0913
        self, is_logged_in, use_staff_user, client, user_client, staff_client
    ):
        """Test that the viewset can delete an object."""

        self.queryset = IntegratedSystem.objects.all()
        (instance, response) = super().test_delete(
            is_logged_in, use_staff_user, client, user_client, staff_client
        )

        if is_logged_in and use_staff_user:
            instance.refresh_from_db()
            assert response.status_code == 204
            assert not instance.is_active
        else:
            assert instance.is_active

    @pytest.mark.parametrize(
        (
            "is_logged_in",
            "use_staff_user",
        ),
        [
            (
                True,
                False,
            ),
            (
                True,
                True,
            ),
            (
                False,
                False,
            ),
        ],
    )
    @pytest.mark.parametrize("with_bad_data", [True, False])
    def test_create(  # noqa: PLR0913
        self,
        with_bad_data,
        is_logged_in,
        use_staff_user,
        client,
        user_client,
        staff_client,
    ):
        """Test that the viewset can create an object."""
        create_data = {
            "description": "a description",
            "api_key": "123456",
        }

        if not with_bad_data:
            create_data["name"] = "System Name"

        response = super().test_create(
            create_data, is_logged_in, use_staff_user, client, user_client, staff_client
        )

        if is_logged_in and use_staff_user:
            assert response.status_code == 201 if not with_bad_data else 400
            assert (
                IntegratedSystem.objects.filter(name="System Name").exists()
                is not with_bad_data
            )
        else:
            assert response.status_code == 403


class TestProductViewSet(AuthVariegatedModelViewSetTest):
    """Tests for the ProductViewSet."""

    viewset_class = ProductViewSet
    factory_class = ActiveProductFactory
    queryset = Product.objects.all()

    list_url = "/api/v0/meta/product/"
    object_url = "/api/v0/meta/product/{}/"

    read_only_serializer_class = ProductSerializer
    read_write_serializer_class = ProductSerializer

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user", "is_active_product"),
        [
            (True, False, True),
            (True, True, True),
            (False, False, True),
            (True, False, False),
            (True, True, False),
            (False, False, False),
        ],
    )
    def test_retrieve(  # noqa: PLR0913
        self,
        is_active_product,
        is_logged_in,
        use_staff_user,
        client,
        user_client,
        staff_client,
    ):
        """
        Test that the viewset can retrieve an object that is either active or possibly
        inactive.
        """

        self.factory_class = (
            ActiveProductFactory if is_active_product else InactiveProductFactory
        )

        super().test_retrieve(
            is_logged_in, use_staff_user, client, user_client, staff_client
        )

    @pytest.mark.parametrize(
        ("is_logged_in", "use_staff_user", "is_active_product"),
        [
            (True, False, True),
            (True, True, True),
            (False, False, True),
            (True, False, False),
            (True, True, False),
            (False, False, False),
        ],
    )
    def test_update(  # noqa: PLR0913
        self,
        is_active_product,
        is_logged_in,
        use_staff_user,
        client,
        user_client,
        staff_client,
    ):
        """Test that the viewset can update an object."""
        self.factory_class = (
            ActiveProductFactory if is_active_product else InactiveProductFactory
        )
        update_data = {"name": "Updated Name"}

        (instance, response) = super().test_update(
            update_data, is_logged_in, use_staff_user, client, user_client, staff_client
        )

        if is_logged_in and use_staff_user:
            if not is_active_product:
                assert instance.name != update_data["name"]
                assert response.status_code == 404
                return

            instance.refresh_from_db()
            assert instance.name == update_data["name"]
        else:
            assert instance.name != update_data["name"]

    @pytest.mark.parametrize(
        (
            "is_logged_in",
            "use_staff_user",
        ),
        [
            (
                True,
                False,
            ),
            (
                True,
                True,
            ),
            (
                False,
                False,
            ),
        ],
    )
    def test_delete(  # noqa: PLR0913
        self, is_logged_in, use_staff_user, client, user_client, staff_client
    ):
        """Test that the viewset can delete an object."""
        self.queryset = Product.objects.all()
        (instance, response) = super().test_delete(
            is_logged_in, use_staff_user, client, user_client, staff_client
        )

        if is_logged_in and use_staff_user:
            instance.refresh_from_db()
            assert response.status_code == 204
            assert not instance.is_active
        else:
            assert instance.is_active

    @pytest.mark.parametrize(
        (
            "is_logged_in",
            "use_staff_user",
        ),
        [
            (
                True,
                False,
            ),
            (
                True,
                True,
            ),
            (
                False,
                False,
            ),
        ],
    )
    @pytest.mark.parametrize("with_bad_data", [True, False])
    def test_create(  # noqa: PLR0913
        self,
        with_bad_data,
        is_logged_in,
        use_staff_user,
        client,
        user_client,
        staff_client,
    ):
        """Test that the viewset can create an object."""
        system = IntegratedSystemFactory.create()
        create_data = {
            "name": "New Name",
            "price": 10.00,
            "sku": "1234567890123",
            "system": system.id,
        }

        if not with_bad_data:
            create_data["description"] = "a description"

        response = super().test_create(
            create_data, is_logged_in, use_staff_user, client, user_client, staff_client
        )

        if is_logged_in and use_staff_user:
            assert response.status_code == 201 if not with_bad_data else 400
            assert Product.objects.filter(name="New Name").exists() is not with_bad_data
        else:
            assert response.status_code == 403
