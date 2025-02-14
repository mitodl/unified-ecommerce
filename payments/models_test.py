"""Tests for payment models."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.http import HttpRequest

import pytest
import pytz
import reversion
from mitol.payment_gateway.payment_utils import quantize_decimal
from reversion.models import Version

from payments import models
from payments.factories import (
    BasketFactory,
    BasketItemFactory,
    DiscountFactory,
    LineFactory,
    OrderFactory,
    TaxRateFactory,
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

    assert models.RedeemedDiscount.objects.filter(
        discount=discount, user=basket.user, order=order
    ).exists()


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
        discount_code=uuid.uuid4(),
    )
    discount_not_used = models.Discount.objects.create(
        amount=10,
        product=unused_product,
        discount_code=uuid.uuid4(),
    )
    basket.discounts.add(discount_used, discount_not_used)
    models.PendingOrder.create_from_basket(basket)

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
        discount_code=uuid.uuid4(),
    )
    discount_not_used = models.Discount.objects.create(
        amount=5,
        product=basket.basket_items.first().product,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        discount_code=uuid.uuid4(),
    )
    basket.discounts.add(discount_used, discount_not_used)
    models.PendingOrder.create_from_basket(basket)

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
        models.RedeemedDiscount.objects.create(
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
    models.RedeemedDiscount.objects.create(
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
        discount_code=uuid.uuid4(),
    )
    discount_2 = models.Discount.objects.create(
        amount=5,
        product=basket_item.product,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        discount_code=uuid.uuid4(),
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
        discount_code=uuid.uuid4(),
    )
    discount_2 = models.Discount.objects.create(
        amount=5,
        integrated_system=basket.integrated_system,
        discount_type=DISCOUNT_TYPE_DOLLARS_OFF,
        discount_code=uuid.uuid4(),
    )
    basket.discounts.add(discount_1, discount_2)

    assert basket_item.discounted_price == (basket_item.base_price - discount_1.amount)


@pytest.mark.parametrize("user_is_in_taxed_country", [True, False])
def test_basket_tax_calculation(user, user_is_in_taxed_country):
    """Test that the tax is calculated correctly."""

    if user_is_in_taxed_country:
        tax_rate = TaxRateFactory.create(country_code=user.profile.country_code)
    else:
        tax_rate = TaxRateFactory.create()

    basket = BasketFactory.create(user=user)

    if user_is_in_taxed_country:
        basket.tax_rate = tax_rate
        basket.save()

    with reversion.create_revision():
        BasketItemFactory.create_batch(2, basket=basket)

    basket.refresh_from_db()

    for item in basket.basket_items.all():
        assert item.tax == (
            item.base_price * (tax_rate.tax_rate / 100)
            if user_is_in_taxed_country
            else 0
        )

    if user_is_in_taxed_country:
        assert basket.tax == sum(
            [
                item.base_price * (tax_rate.tax_rate / 100)
                for item in basket.basket_items.all()
            ]
        )
    else:
        assert basket.tax == 0


def test_basket_tax_calculation_precision_check(user):
    """
    Test that the tax is calculated correctly in the Basket.

    This is a sanity check test with a known tax value to check for introduced
    errors.
    """

    tax_rate = TaxRateFactory.create(
        country_code=user.profile.country_code, tax_rate=10.0
    )
    basket = BasketFactory.create(user=user)
    basket.tax_rate = tax_rate
    basket.save()

    with reversion.create_revision():
        item = BasketItemFactory.create(basket=basket, quantity=1)

    basket.refresh_from_db()

    # Pass tax rate as Decimal(str) - if we use a float, we get a huge mantissa.
    tax_assessed = item.product.price * Decimal("0.1")
    taxed_price = item.product.price + tax_assessed

    assert basket.tax == tax_assessed
    assert basket.total == taxed_price
    assert item.tax == tax_assessed
    assert item.total_price == taxed_price


@pytest.mark.parametrize("user_is_in_taxed_country", [True, False])
def test_order_tax_calculation(user, user_is_in_taxed_country):
    """Test that the tax is calculated correctly."""

    if user_is_in_taxed_country:
        tax_rate = TaxRateFactory.create(country_code=user.profile.country_code)
    else:
        tax_rate = TaxRateFactory.create()

    order = OrderFactory.create(purchaser=user)

    if user_is_in_taxed_country:
        order.tax_rate = tax_rate
        order.save()

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()

    LineFactory.create(
        order=order,
        product_version=product_version,
        discounted_price=product_version.field_dict["price"],
    )

    order.refresh_from_db()

    for item in order.lines.all():
        assert item.tax_money == quantize_decimal(
            item.base_price * (tax_rate.tax_rate / 100)
            if user_is_in_taxed_country
            else 0
        )

    if user_is_in_taxed_country:
        assert order.tax == quantize_decimal(
            sum(
                [
                    item.base_price * (tax_rate.tax_rate / 100)
                    for item in order.lines.all()
                ]
            )
        )
    else:
        assert order.tax == 0


def test_order_tax_calculation_precision_check(user):
    """
    Test that the tax is calculated correctly in the Order.

    This is a sanity check test with a known tax value to check for introduced
    errors.
    """

    tax_rate = TaxRateFactory.create(
        country_code=user.profile.country_code, tax_rate=10.0
    )
    order = OrderFactory.create(purchaser=user, tax_rate=tax_rate)

    with reversion.create_revision():
        product = ProductFactory.create()

    product_version = Version.objects.get_for_object(product).first()

    LineFactory.create(
        order=order,
        product_version=product_version,
        discounted_price=product_version.field_dict["price"],
    )

    order.refresh_from_db()

    # Pass tax rate as Decimal(str) - if we use a float, we get a huge mantissa.
    tax_assessed = product.price * Decimal("0.1")
    taxed_price = product.price + tax_assessed

    # Don't check the order, because we just store that during the checkout process.
    assert order.tax == quantize_decimal(tax_assessed)
    assert order.lines.first().tax == tax_assessed
    assert order.lines.first().total_price == taxed_price


def test_resolve_discount_version_current_version():
    """
    Test that the current version of a Discount instance is returned when no version is specified.
    """
    # Create a Discount instance
    discount = DiscountFactory()

    # Call the method with discount_version=None (current version)
    result = models.Discount.resolve_discount_version(discount, discount_version=None)

    # Assert that the current version is returned
    assert result == discount

def test_resolve_discount_version_no_versions():
    """
    Test that an error is raised when no versions of a Discount instance are found.
    """
    # Create a Discount instance
    discount = DiscountFactory()

    # Call the method with discount_version=None (current version)
    result = models.Discount.resolve_discount_version(discount, discount_version=None)

    # Assert that the current version is returned
    assert result == discount


def test_resolve_discount_version_invalid_version():
    """
    Test that an error is raised when an invalid version is specified.
    """
    # Create a Discount instance
    discount = DiscountFactory()

    # Create a version of the Discount instance
    with reversion.create_revision():
        discount.amount = 50
        discount.save()
        reversion.set_comment("Changed amount to 50")

    # Get the version
    versions = Version.objects.get_for_object(discount)
    version = versions.first()

    # Call the method with an invalid version
    with pytest.raises(TypeError) as exc_info:
        models.Discount.resolve_discount_version(
            discount, discount_version="invalid_version"
        )

    # Assert the correct error message
    assert str(exc_info.value) == "Invalid product version specified"


def test_establish_basket_new_basket():
    """
    Test that a new basket is created when a basket does not already exist for the user and integrated system.
    """
    # Create a user and an integrated system
    user = UserFactory()
    integrated_system = IntegratedSystemFactory()

    # Simulate a request object with the user
    request = HttpRequest()
    request.user = user

    # Call the method
    basket = models.Basket.establish_basket(request, integrated_system)

    # Assert that a new basket was created
    assert basket.user == user
    assert basket.integrated_system == integrated_system
    assert models.Basket.objects.filter(user=user, integrated_system=integrated_system).exists()

def test_establish_basket_existing_basket():
    """
    Test that an existing basket is returned when a basket already exists for the user and integrated system.
    """
    # Create a user, an integrated system, and an existing basket
    user = UserFactory()
    integrated_system = IntegratedSystemFactory()
    existing_basket = BasketFactory(user=user, integrated_system=integrated_system)

    # Simulate a request object with the user
    request = HttpRequest()
    request.user = user

    # Call the method
    basket = models.Basket.establish_basket(request, integrated_system)

    # Assert that the existing basket was returned
    assert basket == existing_basket
    assert models.Basket.objects.filter(user=user, integrated_system=integrated_system).count() == 1

def test_establish_basket_multiple_integrated_systems():
    """
    Test that a new basket is created for each integrated system when multiple integrated systems exist.
    """
    # Create a user and two integrated systems
    user = UserFactory()
    integrated_system1 = IntegratedSystemFactory()
    integrated_system2 = IntegratedSystemFactory()

    # Simulate a request object with the user
    request = HttpRequest()
    request.user = user

    # Call the method for the first integrated system
    basket1 = models.Basket.establish_basket(request, integrated_system1)

    # Call the method for the second integrated system
    basket2 = models.Basket.establish_basket(request, integrated_system2)

    # Assert that two different baskets were created
    assert basket1 != basket2
    assert basket1.integrated_system == integrated_system1
    assert basket2.integrated_system == integrated_system2
    assert models.Basket.objects.filter(user=user).count() == 2

def test_establish_basket_unique_constraint():
    """
    Test that a single basket is created when the method is called multiple times.
    """
    # Create a user and an integrated system
    user = UserFactory()
    integrated_system = IntegratedSystemFactory()

    # Simulate a request object with the user
    request = HttpRequest()
    request.user = user

    # Call the method twice
    basket1 = models.Basket.establish_basket(request, integrated_system)
    basket2 = models.Basket.establish_basket(request, integrated_system)

    # Assert that the same basket was returned both times
    assert basket1 == basket2
    assert models.Basket.objects.filter(user=user, integrated_system=integrated_system).count() == 1