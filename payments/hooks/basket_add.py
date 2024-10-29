"""Add to cart hook implementations for payments."""

import pluggy
from django.db.models import Q
from django.http import HttpRequest

from authentication.api import determine_user_location, get_flagged_countries
from payments.dataclasses import CustomerLocationMetadata
from payments.exceptions import ProductBlockedError
from payments.models import Basket, BlockedCountry, TaxRate
from system_meta.models import Product
from unified_ecommerce.constants import FLAGGED_COUNTRY_BLOCKED, FLAGGED_COUNTRY_TAX

hookimpl = pluggy.HookimplMarker("unified_ecommerce")


class CustomerVerificationHooks:
    """Contains hooks to verify customer information."""

    @hookimpl(wrapper=True, specname="basket_add")
    def locate_customer(self, request: HttpRequest, basket_item: Product):
        """
        Locate the customer.

        We'll need to geolocate the customer for tax and blocked country
        determinations, so this performs this task and puts the necessary data
        in the basket.

        Args:
        - request (HttpRequest): the current request
        - basket_item (Product): the item to add to the basket
        """

        location_meta = CustomerLocationMetadata(
            determine_user_location(
                request,
                get_flagged_countries(FLAGGED_COUNTRY_BLOCKED, product=basket_item),
            ),
            determine_user_location(
                request, get_flagged_countries(FLAGGED_COUNTRY_TAX)
            ),
        )

        basket = Basket.establish_basket(request)
        basket.set_customer_location(location_meta)
        basket.save()

        return (yield)

    @hookimpl(specname="basket_add", tryfirst=True)
    def blocked_country_check(self, request: HttpRequest, basket_item: Product):
        """
        Check to see if the product is blocked for this customer.

        We should have the customer's location stored, so now perform the check
        to see if the product is blocked or not. If it is, we raise an exception
        to stop the process.

        Args:
        - request (HttpRequest): the current request
        - basket_item (Product): the item to add to the basket
        """

        basket = Basket.establish_basket(request)

        blocked_qset = BlockedCountry.objects.filter(
            active=True, country_code=basket.user_blockable_country_code
        ).filter(Q(product__isnull=True) | Q(product=basket_item))

        if blocked_qset.exists():
            errmsg = "Product %s blocked from purchase in country %s"
            raise ProductBlockedError(
                errmsg, basket_item, basket.user_blockable_country_code
            )

    @hookimpl(specname="basket_add", tryfirst=True)
    def taxable_check(self, request: HttpRequest, basket_item: Product):  # noqa: ARG002
        """
        Check to see if the product is taxable for this customer.

        We don't consider particular items taxable or not but we may want to
        change that in the future. (Maybe one day we'll sell gift cards or
        something!)

        Args:
        - request (HttpRequest): the current request
        - basket_item (Product): the item to add to the basket; ignored
        Returns:
        - Applicable TaxRate object or None
        """

        basket = Basket.establish_basket(request)

        taxable_qset = TaxRate.objects.filter(
            active=True, country_code=basket.user_blockable_country_code
        )

        if taxable_qset.exists():
            return taxable_qset.first()

        return None
