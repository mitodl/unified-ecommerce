"""Tests for utility functions in payments."""

import pytest
import pytz
from dateutil import parser

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


def test_parse_supplied_date_with_timezone():
    """
    Test that the supplied date string is parsed correctly when it includes timezone information.
    """
    # Test a date string with timezone information
    datearg = "2023-10-15T12:30:00+05:00"
    result = utils.parse_supplied_date(datearg)

    # Expected result: timezone should be converted to TIME_ZONE
    expected = parser.parse("2023-10-15T07:30:00").replace(tzinfo=pytz.timezone("UTC"))
    assert result == expected


def test_parse_supplied_date_without_timezone():
    """
    Test that the supplied date string is parsed correctly when it does not include timezone information.
    """
    # Test a date string without timezone information
    datearg = "2023-10-15T12:30:00"
    result = utils.parse_supplied_date(datearg)

    # Expected result: timezone should be set to TIME_ZONE
    expected = parser.parse("2023-10-15T12:30:00").replace(tzinfo=pytz.timezone("UTC"))
    assert result == expected


def test_parse_supplied_date_with_invalid_date():
    """
    Test that an invalid date string raises a ValueError.
    """
    # Test an invalid date string
    datearg = "invalid-date"
    with pytest.raises(ValueError):  # noqa: PT011
        utils.parse_supplied_date(datearg)


def test_parse_supplied_date_with_empty_string():
    """
    Test that an empty date string raises a ValueError.
    """
    # Test an empty date string
    datearg = ""
    with pytest.raises(ValueError):  # noqa: PT011
        utils.parse_supplied_date(datearg)


def test_parse_supplied_date_with_only_date():
    """
    Test that the supplied date string is parsed correctly when it only includes the date (no time).
    """
    # Test a date string with only date (no time)
    datearg = "2023-10-15"
    result = utils.parse_supplied_date(datearg)

    # Expected result: time should default to midnight, timezone set to TIME_ZONE
    expected = parser.parse("2023-10-15T00:00:00").replace(tzinfo=pytz.timezone("UTC"))
    assert result == expected


def test_parse_supplied_date_with_different_timezone():
    """
    Test that the supplied date string is parsed correctly when it includes a different timezone.
    """
    # Test a date string with a different timezone
    datearg = "2023-10-15T12:30:00-07:00"
    result = utils.parse_supplied_date(datearg)

    # Expected result: timezone should be converted to TIME_ZONE
    expected = parser.parse("2023-10-15T19:30:00").replace(tzinfo=pytz.timezone("UTC"))
    assert result == expected
