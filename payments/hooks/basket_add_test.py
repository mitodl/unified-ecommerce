"""Tests for the basket-add hook."""

import ipaddress

import faker
import pytest
import reversion
from django.urls import reverse
from mitol.geoip.factories import GeonameFactory, NetBlockIPv4Factory
from rest_framework.test import APIClient

from payments.constants import GEOLOCATION_TYPE_GEOIP
from payments.factories import (
    BasketFactory,
    BlockedCountryFactory,
    ProductFactory,
    TaxRateFactory,
)

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


@pytest.fixture()
def basket():
    """Create a basket."""
    return BasketFactory.create()


@pytest.fixture()
def maxmimd_resolvable_ip():
    """Create an IP, and then make sure there are mappings for it."""

    geoname = GeonameFactory.create()
    netblock = NetBlockIPv4Factory.create(geoname_id=geoname.geoname_id)
    rand_decimal_ip = FAKE.random_int(
        netblock.decimal_ip_start, netblock.decimal_ip_end
    )

    return (
        str(ipaddress.IPv4Address(rand_decimal_ip)),
        geoname.country_iso_code,
    )


@pytest.fixture()
def user_client_and_basket():
    """Create a basket, and a user client with the basket's user."""

    basket = BasketFactory.create()

    user_client = APIClient()
    user_client.force_login(basket.user)

    return user_client, basket


def test_basket_add_wrapper(mocker, user_client_and_basket, maxmimd_resolvable_ip):
    """
    Test that the wrapper for the basket_add hook adds the data as we expect.

    Also test that the blocked countries and taxable checks get run.
    """

    user_client, basket = user_client_and_basket

    mocked_bcc = mocker.patch("payments.api.check_blocked_countries")
    mocked_tcc = mocker.patch("payments.api.check_taxable")

    with reversion.create_revision():
        product = ProductFactory.create(system=basket.integrated_system)

    url = reverse(
        "v0:create_from_product", args=[basket.integrated_system.slug, product.sku]
    )

    resp = user_client.post(url, REMOTE_ADDR=maxmimd_resolvable_ip[0])

    assert resp.status_code == 201

    basket.refresh_from_db()

    mocked_bcc.assert_called_once()
    mocked_tcc.assert_called_once()

    assert basket.user_taxable_geolocation_type == GEOLOCATION_TYPE_GEOIP
    assert basket.user_taxable_country_code == maxmimd_resolvable_ip[1]
    assert basket.user_blockable_geolocation_type == GEOLOCATION_TYPE_GEOIP
    assert basket.user_blockable_country_code == maxmimd_resolvable_ip[1]
    assert basket.user_ip == maxmimd_resolvable_ip[0]


@pytest.mark.parametrize("user_in_country", [True, False])
def test_basket_blocked_country(
    mocker, user_client_and_basket, maxmimd_resolvable_ip, user_in_country
):
    """Test that the blocked country check works."""

    user_client, basket = user_client_and_basket

    mocker.patch("payments.api.check_taxable")

    with reversion.create_revision():
        product = ProductFactory.create(system=basket.integrated_system)

    url = reverse(
        "v0:create_from_product", args=[basket.integrated_system.slug, product.sku]
    )

    country_code = (
        maxmimd_resolvable_ip[1] if user_in_country else FAKE.unique.country_code()
    )
    BlockedCountryFactory.create(country_code=country_code)

    resp = user_client.post(url, REMOTE_ADDR=maxmimd_resolvable_ip[0])

    assert resp.status_code == 451 if user_in_country else 201


def test_basket_blocked_country_product(
    mocker, user_client_and_basket, maxmimd_resolvable_ip
):
    """Test that the blocked country check works for a specific product."""

    user_client, basket = user_client_and_basket

    mocker.patch("payments.api.check_taxable")

    with reversion.create_revision():
        product = ProductFactory.create(system=basket.integrated_system)
        product_not_blocked = ProductFactory.create(system=basket.integrated_system)

    country_code = maxmimd_resolvable_ip[1]
    BlockedCountryFactory.create(country_code=country_code, product=product)

    url = reverse(
        "v0:create_from_product", args=[basket.integrated_system.slug, product.sku]
    )

    resp = user_client.post(url, REMOTE_ADDR=maxmimd_resolvable_ip[0])

    assert resp.status_code == 451

    url = reverse(
        "v0:create_from_product",
        args=[basket.integrated_system.slug, product_not_blocked.sku],
    )

    resp = user_client.post(url, REMOTE_ADDR=maxmimd_resolvable_ip[0])

    assert resp.status_code == 201


@pytest.mark.parametrize("user_in_country", [True, False])
def test_basket_add_tax_collection(
    mocker, user_client_and_basket, maxmimd_resolvable_ip, user_in_country
):
    """Test that the blocked country check works."""

    user_client, basket = user_client_and_basket

    mocker.patch("payments.api.check_blocked_countries")

    with reversion.create_revision():
        product = ProductFactory.create(system=basket.integrated_system)

    url = reverse(
        "v0:create_from_product", args=[basket.integrated_system.slug, product.sku]
    )

    country_code = (
        maxmimd_resolvable_ip[1] if user_in_country else FAKE.unique.country_code()
    )
    tax_rate = TaxRateFactory.create(country_code=country_code)

    resp = user_client.post(url, REMOTE_ADDR=maxmimd_resolvable_ip[0])
    basket.refresh_from_db()

    assert resp.status_code == 201
    assert basket.tax_rate == (tax_rate if user_in_country else None)

    if user_in_country:
        assert basket.tax > 0
