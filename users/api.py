"""API functions for users"""

from django.conf import settings
from django.db.models import Q
from ipware import get_client_ip
from mitol.geoip.api import ip_to_country_code

from payments.constants import (
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_NONE,
    GEOLOCATION_TYPE_PROFILE,
)
from payments.models import BlockedCountry, TaxRate
from unified_ecommerce.constants import (
    FLAGGED_COUNTRY_BLOCKED,
    FLAGGED_COUNTRY_TAX,
    FLAGGED_COUNTRY_TYPES,
)
from users.dataclasses import CustomerCalculatedLocation


def get_flagged_countries(flag_type, product=None):
    """
    Return the list of flagged countries.

    A country can be flagged for a particular item; passing that in as a Product
    will return globally-flagged countries and any that are flagged for that
    Product. (This only applies to blocks for now.)

    Args:
    - flag_type (string): one of FLAGGED_COUNTRY_TYPES
    - product (Product): a product to also consider
    Returns:
    - list of string: country codes that are blocked
    """

    if flag_type not in FLAGGED_COUNTRY_TYPES:
        errmsg = "Invalid flag type %s"
        raise ValueError(errmsg, flag_type)

    qset = None

    if flag_type == FLAGGED_COUNTRY_BLOCKED:
        qset = BlockedCountry.objects

        if product:
            qset = qset.filter(Q(product__isnull=True) | Q(product=product))
        else:
            qset = qset.filter(product__isnull=True)

    elif flag_type == FLAGGED_COUNTRY_TAX:
        qset = TaxRate.objects

    return qset.values_list("country_code", flat=True).all() if qset else []


def determine_user_location(
    request, flagged_countries=None
) -> CustomerCalculatedLocation:
    """
    Determine where the user is, based on various details.

    The user's location can be determined in a few ways:
    - We can look their IP address up via the MaxMind GeoIP database
    - Their profile can contain a country code

    This makes a determination of where the user is based on these two checks:
    - If either check returns a country that is flagged, then that country is
      used as their location.
    - Otherwise, prefer the IP address lookup over the profile code.

    Country codes are flagged if the country requires tax assessment or is
    blocked from purchasing certain items.

    If MITOL_UE_FORCE_PROFILE_COUNTRY is set, then this will _always_ return the
    country code listed in the profile.

    Args:
    - request (Request): the current request
    - flagged_countries (None or list): a list of flagged countries

    Returns:
    - CustomerCalculatedLocation:
        ISO country code (ISO 3166 alpha2) and one of the GEOLOCATION_TYPE constants
    """

    if not request.user.is_authenticated:
        errmsg = "User is unauthenticated, can't determine location"
        raise ValueError(errmsg)

    profile_code = (
        str(request.user.profile.country_code) if request.user.profile else None
    )

    if settings.MITOL_UE_FORCE_PROFILE_COUNTRY:
        return (profile_code, GEOLOCATION_TYPE_PROFILE)

    user_ip, _ = get_client_ip(request)
    geoip_code = ip_to_country_code(user_ip)

    if flagged_countries:
        if profile_code in flagged_countries:
            return CustomerCalculatedLocation(
                profile_code, GEOLOCATION_TYPE_PROFILE, user_ip
            )
        if geoip_code in flagged_countries:
            return CustomerCalculatedLocation(
                geoip_code, GEOLOCATION_TYPE_GEOIP, user_ip
            )

    if geoip_code:
        return CustomerCalculatedLocation(geoip_code, GEOLOCATION_TYPE_GEOIP, user_ip)

    if profile_code:
        return CustomerCalculatedLocation(
            profile_code, GEOLOCATION_TYPE_PROFILE, user_ip
        )

    return CustomerCalculatedLocation(None, GEOLOCATION_TYPE_NONE, user_ip)
