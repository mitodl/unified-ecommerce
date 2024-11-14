"""Utility functions for payments."""

from decimal import Decimal

from system_meta.models import Product
from unified_ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)


def product_price_with_discount(discount, product: Product) -> Decimal:
    """
    Return the price of the product with the discount applied

    Args:
        discount (Discount): The discount to apply to the product
        product (Product): The product to apply the discount to
    Returns:
        Decimal: The price of the product with the discount applied, or the price of the
        product if the discount type is not recognized.
    """
    if discount.discount_type == DISCOUNT_TYPE_PERCENT_OFF:
        return Decimal(product.price * (1 - discount.amount / 100))
    if discount.discount_type == DISCOUNT_TYPE_DOLLARS_OFF:
        return Decimal(product.price - discount.amount)
    if discount.discount_type == DISCOUNT_TYPE_FIXED_PRICE:
        return Decimal(discount.amount)
    return product.price
