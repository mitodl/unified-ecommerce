"""Tests for utility functions in payments."""

import pytest

from payments import models, utils
from system_meta.factories import ProductFactory
from unified_ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "discount_type",
    [DISCOUNT_TYPE_PERCENT_OFF, DISCOUNT_TYPE_DOLLARS_OFF, DISCOUNT_TYPE_FIXED_PRICE],
)
def test_product_price_with_discount(discount_type):
    """
    Test that the product price with discount is calculated correctly.

    Args:
        discount_type (str): String representing the type of discount to apply to the product
    """
    product = ProductFactory.create(
        price=100,
    )
    discount = models.Discount.objects.create(
        amount=10,
        discount_type=discount_type,
    )
    if discount_type == DISCOUNT_TYPE_PERCENT_OFF:
        assert utils.product_price_with_discount(discount, product) == 90
    if discount_type == DISCOUNT_TYPE_DOLLARS_OFF:
        assert utils.product_price_with_discount(discount, product) == 90
    if discount_type == DISCOUNT_TYPE_FIXED_PRICE:
        assert utils.product_price_with_discount(discount, product) == 10
