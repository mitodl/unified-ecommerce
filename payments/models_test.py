"""Tests for payment models."""

import pytest
import reversion

from payments import models
from payments.factories import BasketFactory, BasketItemFactory, LineFactory
from system_meta.factories import ProductVersionFactory

pytestmark = [pytest.mark.django_db]


def test_basket_compare_to_order_match():
    """
    Test that comparing an order to a basket works if they match.

    We consider the basket to match the order if it has the same number of items
    and the same products attached to it. In this case, the order and basket
    should match.
    """

    basket = BasketFactory.create()
    with reversion.create_revision():
        BasketItemFactory.create_batch(2, basket=basket)

    order = models.PendingOrder.create_from_basket(basket)

    assert basket.compare_to_order(order)


@pytest.mark.parametrize(
    ("add_or_del", "in_basket"),
    [
        (True, False),
        (True, True),
        (False, True),
        (False, False),
    ],
)
def test_basket_compare_to_order_line_mismatch(add_or_del, in_basket):
    """
    Test that comparing an order to a basket works properly. In this case, force
    the basket to not compare by adding or removing a line in the Order or in
    the Basket, depending.
    """

    basket = BasketFactory.create()
    with reversion.create_revision():
        BasketItemFactory.create_batch(2, basket=basket)

    order = models.PendingOrder.create_from_basket(basket)

    if in_basket:
        if add_or_del:
            product_version = ProductVersionFactory.create()
            LineFactory.create(
                order=order,
                product_version=ProductVersionFactory.create(),
                discounted_price=product_version.field_dict["price"],
            )
        else:
            order.lines.first().delete()
    elif add_or_del:
        BasketItemFactory.create(basket=basket)
    else:
        basket.basket_items.first().delete()

    basket.refresh_from_db()
    order.refresh_from_db()

    assert not basket.compare_to_order(order)
