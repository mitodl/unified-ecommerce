"""Tests for payment models."""

from datetime import datetime, timedelta

import pytest
import pytz
import reversion

from payments import models
from payments.factories import (
    BasketFactory,
    BasketItemFactory,
    LineFactory,
    OrderFactory,
)
from system_meta.factories import (
    IntegratedSystemFactory,
    ProductFactory,
    ProductVersionFactory,
)
from unified_ecommerce import settings
from unified_ecommerce.constants import DISCOUNT_TYPE_DOLLARS_OFF
from unified_ecommerce.factories import UserFactory

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

def test_redeemed_discounts_created_when_creating_pending_order_from_basket():
    """
    Test that redeemed discounts are created when creating a pending order from a basket.
    """

    basket = BasketFactory.create()
    with reversion.create_revision():
        BasketItemFactory.create_batch(2, basket=basket)
    discount = models.Discount.objects.create(
        amount=10,
        product=basket.basket_items.first().product,
    )
    basket.discounts.add(discount)
    order = models.PendingOrder.create_from_basket(basket)

    assert models.RedeemedDiscount.objects.filter(discount=discount, user=basket.user, order=order).exists()
    
def test_unused_discounts_do_not_create_redeemed_discounts_when_creating_pending_order_from_basket():
    """
    Test that redeemed discounts are not created when creating a pending order from a basket if the discount is not used.
    """

    basket = BasketFactory.create()
    unused_product = ProductFactory.create()
    with reversion.create_revision():
        BasketItemFactory.create_batch(2, basket=basket)
    discount_used = models.Discount.objects.create(
        amount=10,
        product=basket.basket_items.first().product,
    )
    discount_not_used = models.Discount.objects.create(
        amount=10,
        product=unused_product,
    )
    basket.discounts.add(discount_used, discount_not_used)
    order = models.PendingOrder.create_from_basket(basket)

    assert models.RedeemedDiscount.objects.filter(user=basket.user).count() == 1
    assert basket.discounts.count() == 1
    
def test_only_best_discounts_create_redeemed_discounts_when_creating_pending_order_from_basket():
    """
    Test that only the best discounts result in RedeemedDiscounts when creating a pending order from a basket.
    """

    basket = BasketFactory.create()
    with reversion.create_revision():
        BasketItemFactory.create_batch(2, basket=basket)
    discount_used = models.Discount.objects.create(
        amount=10,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        product=basket.basket_items.first().product,
    )
    discount_not_used = models.Discount.objects.create(
        amount=5,
        product=basket.basket_items.first().product,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
    )
    basket.discounts.add(discount_used, discount_not_used)
    order = models.PendingOrder.create_from_basket(basket)

    assert models.RedeemedDiscount.objects.filter(user=basket.user).count() == 1

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


@pytest.mark.parametrize("is_none", [True, False])
def test_discount_with_product_value_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    product = None if is_none else basket_item.product
    discount = models.Discount.objects.create(
        product=product,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)


@pytest.mark.parametrize("is_none", [True, False])
def test_discount_with_user_value_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    discount = models.Discount.objects.create(
        amount=10,
    )
    if not is_none:
        basket_item.basket.user.discounts.add(discount)
    assert discount.is_valid(basket_item.basket)


@pytest.mark.parametrize("is_none", [True, False])
def test_discount_with_integrated_system_value_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    integrated_system = None if is_none else basket_item.basket.integrated_system
    discount = models.Discount.objects.create(
        integrated_system=integrated_system,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)


@pytest.mark.parametrize("is_none", [True, False])
def test_discount_with_max_redemptions_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    discount = models.Discount.objects.create(
        max_redemptions=2,
        amount=10,
    )
    if not is_none:
        order = OrderFactory.create(purchaser=basket_item.basket.user)
        redeemed_discount = models.RedeemedDiscount.objects.create(
            discount=discount,
            user=basket_item.basket.user,
            order=order,
        )
    assert discount.is_valid(basket_item.basket)


@pytest.mark.parametrize("is_none", [True, False])
def test_discount_with_activation_date_in_past_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()
    activation_date = (
        None
        if is_none
        else datetime.now(tz=pytz.timezone(settings.TIME_ZONE)) - timedelta(days=100)
    )
    discount = models.Discount.objects.create(
        activation_date=activation_date,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)


@pytest.mark.parametrize("is_none", [True, False])
def test_discount_with_expiration_date_in_future_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()
    expiration_date = (
        None
        if is_none
        else datetime.now(tz=pytz.timezone(settings.TIME_ZONE)) + timedelta(days=100)
    )
    discount = models.Discount.objects.create(
        expiration_date=expiration_date,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)


def test_discount_with_unmatched_product_value_is_not_valid_for_basket():
    """Test that a discount is not valid for a basket."""
    basket_item = BasketItemFactory.create()

    product = ProductFactory.create()
    discount = models.Discount.objects.create(
        product=product,
        amount=10,
    )
    assert not discount.is_valid(basket_item.basket)


def test_discount_with_unmatched_user_value_is_not_valid_for_basket():
    """Test that a discount is not valid for a basket."""
    basket_item = BasketItemFactory.create()

    discount = models.Discount.objects.create(
        amount=10,
    )
    user = UserFactory.create()
    user.discounts.add(discount)
    assert not discount.is_valid(basket_item.basket)


def test_discount_with_unmatched_integrated_system_value_is_not_valid_for_basket():
    """Test that a discount is not valid for a basket."""
    basket_item = BasketItemFactory.create()
    integrated_system = IntegratedSystemFactory.create()

    discount = models.Discount.objects.create(
        integrated_system=integrated_system,
        amount=10,
    )
    assert not discount.is_valid(basket_item.basket)


def test_discount_with_max_redemptions_is_not_valid_for_basket():
    """Test that a discount is not valid for a basket."""
    basket_item = BasketItemFactory.create()

    discount = models.Discount.objects.create(
        max_redemptions=1,
        amount=10,
    )

    order = OrderFactory.create(purchaser=basket_item.basket.user)
    redeemed_discount = models.RedeemedDiscount.objects.create(
        discount=discount,
        user=basket_item.basket.user,
        order=order,
    )
    assert not discount.is_valid(basket_item.basket)


def test_discount_with_activation_date_in_future_is_not_valid_for_basket():
    """Test that a discount is not valid for a basket."""
    basket_item = BasketItemFactory.create()
    activation_date = datetime.now(tz=pytz.timezone(settings.TIME_ZONE)) + timedelta(
        days=100
    )
    discount = models.Discount.objects.create(
        activation_date=activation_date,
        amount=10,
    )
    assert not discount.is_valid(basket_item.basket)


def test_discount_with_expiration_date_in_past_is_not_valid_for_basket():
    """Test that a discount is not valid for a basket."""
    basket_item = BasketItemFactory.create()
    expiration_date = datetime.now(tz=pytz.timezone(settings.TIME_ZONE)) - timedelta(
        days=100
    )
    discount = models.Discount.objects.create(
        expiration_date=expiration_date,
        amount=10,
    )
    assert not discount.is_valid(basket_item.basket)


def test_discounted_price_for_multiple_discounts_for_product():
    """Test that the discounted price is calculated correctly."""
    basket_item = BasketItemFactory.create()
    basket = BasketFactory.create()
    basket.basket_items.add(basket_item)
    discount_1 = models.Discount.objects.create(
        amount=10,
        product=basket_item.product,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
    )
    discount_2 = models.Discount.objects.create(
        amount=5,
        product=basket_item.product,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
    )
    basket.discounts.add(discount_1, discount_2)

    assert basket_item.discounted_price == (basket_item.base_price - discount_1.amount)


def test_discounted_price_for_multiple_discounts_for_integrated_system():
    """Test that the discounted price is calculated correctly."""
    basket_item = BasketItemFactory.create()
    basket = BasketFactory.create()
    basket.basket_items.add(basket_item)
    discount_1 = models.Discount.objects.create(
        amount=10,
        integrated_system=basket.integrated_system,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
    )
    discount_2 = models.Discount.objects.create(
        amount=5,
        integrated_system=basket.integrated_system,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
    )
    basket.discounts.add(discount_1, discount_2)

    assert basket_item.discounted_price == (basket_item.base_price - discount_1.amount)
