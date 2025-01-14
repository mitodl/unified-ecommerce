"""View tests for the v0 API."""

import pytest

from payments.factories import BasketFactory, DiscountFactory, ProductFactory
from payments.models import Basket
from system_meta.factories import ActiveIntegratedSystemFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("existing_basket", "add_discount", "bad_product"),
    [(True, False, False), (False, True, False), (False, False, True)],
)
def test_create_basket_with_products(
    mocker, user, user_client, existing_basket, add_discount, bad_product
):
    """Test creating a basket with products."""

    mocker.patch("payments.api.send_pre_sale_webhook")
    system = ActiveIntegratedSystemFactory()
    if bad_product:
        products = ProductFactory.create_batch(size=2)
    else:
        products = ProductFactory.create_batch(size=2, system=system)

    basket = (
        BasketFactory(user=user, integrated_system=system) if existing_basket else None
    )

    url = "/api/v0/payments/baskets/create_with_products/"
    payload = {
        "system_slug": system.slug,
        "skus": [{"sku": product.sku, "quantity": 1} for product in products],
    }

    if add_discount:
        discount = DiscountFactory(discount_type="fixed-price", amount=100)
        payload["discount_code"] = discount.discount_code

    response = user_client.post(
        url,
        data=payload,
    )

    if bad_product:
        assert response.status_code == 404
        return

    assert response.status_code == 200

    basket_id = response.data["id"]
    assert Basket.objects.get(id=basket_id).basket_items.count() == 2

    if existing_basket:
        assert basket_id == basket.id

    if add_discount:
        assert discount in Basket.objects.get(id=basket_id).discounts.all()
