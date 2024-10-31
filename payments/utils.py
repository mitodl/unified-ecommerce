from unified_ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
)


def product_price_with_discount(discount, product):
    """Return the price of the product with the discount applied"""
    if discount.discount_type == DISCOUNT_TYPE_PERCENT_OFF:
        return product.price * (1 - discount.amount / 100)
    if discount.discount_type == DISCOUNT_TYPE_DOLLARS_OFF:
        return product.price - discount.amount
    if discount.discount_type == DISCOUNT_TYPE_FIXED_PRICE:
        return discount.amount
    return product.price
