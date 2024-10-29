"""Tests for the authentication app APIs"""

import ipaddress
import random

import faker
import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from mitol.geoip.factories import GeonameFactory, NetBlockIPv4Factory

from authentication.api import determine_user_location, get_flagged_countries
from authentication.models import UserProfile
from payments.factories import BlockedCountryFactory, ProductFactory, TaxRateFactory
from unified_ecommerce.constants import FLAGGED_COUNTRY_BLOCKED, FLAGGED_COUNTRY_TAX
from unified_ecommerce.factories import UserFactory

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


@pytest.mark.parametrize("with_product", [True, False])
def test_blocked_country_list(with_product):
    """Test the get_flagged_countries list generation for blocked countries."""

    countries = BlockedCountryFactory.create_batch(5)

    if with_product:
        product = ProductFactory.create()
        BlockedCountryFactory.create(product=product)
        assert (
            len(get_flagged_countries(FLAGGED_COUNTRY_BLOCKED, product))
            == len(countries) + 1
        )

    assert len(get_flagged_countries(FLAGGED_COUNTRY_BLOCKED)) == len(countries)


@pytest.mark.parametrize("with_product", [True, False])
def test_tax_country_list(with_product):
    """Test the get_flagged_countries list generation for tax countries."""

    countries = [
        TaxRateFactory.create(country_code=FAKE.unique.country_code()) for _ in range(5)
    ]

    if with_product:
        # TaxRates don't apply only to products, so make sure get_flagged_countries
        # doesn't do something weird here.
        product = ProductFactory.create()
        assert len(get_flagged_countries(FLAGGED_COUNTRY_TAX, product)) == len(
            countries
        )

    assert len(get_flagged_countries(FLAGGED_COUNTRY_TAX)) == len(countries)


@pytest.mark.parametrize(
    (
        "profile_netblock_match",
        "flag_type",
        "with_product",
    ),
    [
        (True, FLAGGED_COUNTRY_BLOCKED, False),
        (False, FLAGGED_COUNTRY_BLOCKED, False),
        (True, FLAGGED_COUNTRY_TAX, False),
        (False, FLAGGED_COUNTRY_TAX, False),
        (True, FLAGGED_COUNTRY_BLOCKED, True),
        (False, FLAGGED_COUNTRY_BLOCKED, True),
    ],
)
def test_determine_user_location(profile_netblock_match, flag_type, with_product):
    """Test that the user location determination works OK."""

    flag_factory = (
        BlockedCountryFactory
        if flag_type == FLAGGED_COUNTRY_BLOCKED
        else TaxRateFactory
    )

    product = ProductFactory.create() if with_product else None

    country_code = FAKE.unique.country_code()
    geoname = GeonameFactory.create(country_iso_code=country_code)
    netblock = NetBlockIPv4Factory.create(geoname_id=geoname.geoname_id)

    if not profile_netblock_match:
        country_code = FAKE.unique.country_code()

    user = UserFactory.create()
    UserProfile.objects.create(country_code=country_code, user=user).save()
    user.refresh_from_db()

    request = RequestFactory().get("/request")
    request.user = user
    request.META["REMOTE_ADDR"] = str(
        ipaddress.IPv4Address(netblock.decimal_ip_start + random.randrange(1, 250))  # noqa: S311
    )

    # Force the country codes here to be unique
    [flag_factory.create(country_code=FAKE.unique.country_code()) for _ in range(5)]

    assert (
        determine_user_location(request, get_flagged_countries(flag_type))
        == user.profile.country_code
        if profile_netblock_match
        else geoname.country_iso_code
    )

    flagged_country = flag_factory.create(country_code=country_code)

    assert determine_user_location(request, get_flagged_countries(flag_type)) == str(
        flagged_country.country_code
    )

    if with_product:
        # Create a blocked country for the product that doesn't match the user
        flagged_country_product = flag_factory.create(
            country_code=FAKE.unique.country_code(), product=product
        )
        assert determine_user_location(
            request, get_flagged_countries(flag_type, product)
        ) != str(flagged_country_product.country_code)

        # Now, create a blocked country w/ product that does match
        flagged_country_product = flag_factory.create(
            country_code=user.profile.country_code, product=product
        )
        assert determine_user_location(
            request, get_flagged_countries(flag_type, product)
        ) == str(flagged_country_product.country_code)


def test_determine_user_location_logged_out():
    """Test that the user location code fails when there's no session."""

    request = RequestFactory().get("/request")
    request.user = AnonymousUser()

    with pytest.raises(ValueError, match=r".*unauth.*"):
        determine_user_location(request)
