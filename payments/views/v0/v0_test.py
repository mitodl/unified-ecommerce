"""View tests for the v0 API."""

import pytest

from payments.factories import ProductFactory
from payments.models import Basket
from system_meta.factories import ActiveIntegratedSystemFactory

pytestmark = pytest.mark.django_db


def test_create_basket_with_products(mocker, user_client):
    """Test creating a basket with products."""

    mocker.patch("payments.api.send_pre_sale_webhook")
    system = ActiveIntegratedSystemFactory()
    products = ProductFactory.create_batch(size=2, system=system)

    url = "/api/v0/payments/baskets/create_with_products/"
    response = user_client.post(
        url,
        data={
            "system_slug": system.slug,
            "skus": [{"sku": product.sku, "quantity": 1} for product in products],
        },
    )
    assert response.status_code in (
        200,
        201,
    )

    basket_id = response.data["id"]
    assert Basket.objects.get(id=basket_id).basket_items.count() == 2
