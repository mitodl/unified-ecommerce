"""Add to cart hook implementations for payments."""

import logging

import pluggy
from django.db.models import Q

from payments.dataclasses import CustomerLocationMetadata
from payments.exceptions import ProductBlockedError
from unified_ecommerce.constants import FLAGGED_COUNTRY_BLOCKED, FLAGGED_COUNTRY_TAX

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

        from users.api import determine_user_location, get_flagged_countries

        log.debug("locate_customer: running for %s", request.user)

        location_meta = CustomerLocationMetadata(
            determine_user_location(
                request,
                get_flagged_countries(FLAGGED_COUNTRY_BLOCKED, product=basket_item),
            ),
            determine_user_location(
                request, get_flagged_countries(FLAGGED_COUNTRY_TAX)
            ),
        )

        basket.set_customer_location(location_meta)
        basket.save()

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

        from payments.models import BlockedCountry

        log.debug("blocked_country_check: checking for blockages for %s", basket.user)

        blocked_qset = BlockedCountry.objects.filter(
            country_code=basket.user_blockable_country_code
        ).filter(Q(product__isnull=True) | Q(product=basket_item))

        if blocked_qset.exists():
            log.debug("blocked_country_check: user is blocked")
            errmsg = "Product %s blocked from purchase in country %s"
            raise ProductBlockedError(
                errmsg, basket_item, basket.user_blockable_country_code
            )

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

        from payments.models import TaxRate

        log.debug("taxable_check: checking for tax for %s", basket.user)

        taxable_qset = TaxRate.objects.filter(
            country_code=basket.user_blockable_country_code
        )

        if taxable_qset.exists():
            taxrate = taxable_qset.first()
            basket.tax_rate = taxrate
            log.debug("taxable_check: charging the tax for %s", taxrate)
