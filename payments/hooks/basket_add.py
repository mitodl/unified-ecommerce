"""Add to cart hook implementations for payments."""

import logging

import pluggy

hookimpl = pluggy.HookimplMarker("unified_ecommerce")
log = logging.getLogger(__name__)


class CustomerVerificationHooks:
    """Contains hooks to verify customer information."""

    @hookimpl(wrapper=True, specname="basket_add")
    def locate_customer(self, request, basket, basket_item):
        """
        Locate the customer.

        We'll need to geolocate the customer for tax and blocked country
        determinations, so this performs this task and puts the necessary data
        in the basket.

        Args:
        - request (HttpRequest): the current request
        - basket (Basket): the current basket
        - basket_item (Product): the item to add to the basket
        """

        from payments.api import locate_customer_for_basket

        locate_customer_for_basket(request, basket, basket_item)

        return (yield)

    @hookimpl(specname="basket_add", tryfirst=True)
    def blocked_country_check(self, request, basket, basket_item):  # noqa: ARG002
        """
        Check to see if the product is blocked for this customer.

        We should have the customer's location stored, so now perform the check
        to see if the product is blocked or not. If it is, we raise an exception
        to stop the process.

        Try this one first so we can kick the user out if they're blocked.

        Args:
        - request (HttpRequest): the current request
        - basket (Basket): the current basket
        - basket_item (Product): the item to add to the basket
        """
        from payments.api import (
            check_blocked_countries,
        )

        check_blocked_countries(basket, basket_item)

    @hookimpl(specname="basket_add", trylast=True)
    def taxable_check(self, request, basket, basket_item):  # noqa: ARG002
        """
        Check to see if the product is taxable for this customer.

        We don't consider particular items taxable or not but we may want to
        change that in the future. (Maybe one day we'll sell gift cards or
        something!) So, this really applies to the basket - if there's an
        applicable rate, then we tack it on to the basket.

        Args:
        - request (HttpRequest): the current request
        - basket (Basket): the current basket
        - basket_item (Product): the item to add to the basket; ignored
        Returns:
        - Applicable TaxRate object or None
        """
        from payments.api import (
            check_taxable,
        )

        check_taxable(basket)
