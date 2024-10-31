"""Tests for payment models."""

from datetime import datetime, timedelta
import pytest
import reversion
import pytz

from payments import models
from payments.factories import BasketFactory, BasketItemFactory, LineFactory, OrderFactory
from system_meta.factories import IntegratedSystemFactory, ProductFactory, ProductVersionFactory
from unified_ecommerce import settings
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

@pytest.mark.parametrize(
    "is_none", [True, False]
)
def test_discount_with_product_value_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    product = None if is_none else basket_item.product
    discount = models.Discount.objects.create(
        product=product,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)

@pytest.mark.parametrize(
    "is_none", [True, False]
)
def test_discount_with_user_value_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    discount = models.Discount.objects.create(
        amount=10,
    )
    if not is_none:
        basket_item.basket.user.discounts.add(discount)
    assert discount.is_valid(basket_item.basket)
  
@pytest.mark.parametrize(
    "is_none", [True, False]
)  
def test_discount_with_integrated_system_value_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()

    integrated_system = None if is_none else basket_item.basket.integrated_system
    discount = models.Discount.objects.create(
        integrated_system=integrated_system,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)

@pytest.mark.parametrize(
    "is_none", [True, False]
)
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

@pytest.mark.parametrize(
    "is_none", [True, False]
)
def test_discount_with_activation_date_in_past_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()
    activation_date = None if is_none else datetime.now(tz=pytz.timezone(settings.TIME_ZONE)) - timedelta(
        days=100
    )
    discount = models.Discount.objects.create(
        activation_date=activation_date,
        amount=10,
    )
    assert discount.is_valid(basket_item.basket)

@pytest.mark.parametrize(
    "is_none", [True, False]
)
def test_discount_with_expiration_date_in_future_is_valid_for_basket(is_none):
    """Test that a discount is valid for a basket."""
    basket_item = BasketItemFactory.create()
    expiration_date = None if is_none else datetime.now(tz=pytz.timezone(settings.TIME_ZONE)) + timedelta(
        days=100
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
