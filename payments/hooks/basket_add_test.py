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
from unified_ecommerce.test_utils import create_xuserinfo_header

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


@pytest.fixture()  # noqa: PT001, RUF100
def basket():
    """Create a basket."""
    return BasketFactory.create()


@pytest.fixture()  # noqa: PT001, RUF100
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


@pytest.fixture()  # noqa: PT001, RUF100
def user_client_and_basket():
    """Create a basket, and a user client with the basket's user."""

    basket = BasketFactory.create()

    user_client = APIClient(headers=create_xuserinfo_header(basket.user))
    user_client.force_login(basket.user)

    return user_client, basket


def mock_basket_add_hook_steps(mocker, exceptfor: str | None = None):
    """
    Mock the steps in the basket_add hook, except for the one specified.

    Args:
    - mocker: The mocker fixture
    - exceptfor: The name of the step to skip
    Returns:
    - A dictionary of the mocked steps
    """

    return {
        "check_blocked_countries": mocker.patch("payments.api.check_blocked_countries")
        if exceptfor != "check_blocked_countries"
        else None,
        "check_taxable": mocker.patch("payments.api.check_taxable")
        if exceptfor != "check_taxable"
        else None,
        "send_pre_sale_webhook": mocker.patch("payments.api.send_pre_sale_webhook")
        if exceptfor != "send_pre_sale_webhook"
        else None,
    }


@pytest.fixture()  # noqa: PT001, RUF100
def basket_add_hook_steps(mocker):
    """Mock the steps in the basket_add hook."""

    return mock_basket_add_hook_steps(mocker)


def test_basket_add_wrapper(
    basket_add_hook_steps, user_client_and_basket, maxmimd_resolvable_ip
):
    """
    Test that the wrapper for the basket_add hook adds the data as we expect.

    Also test that the blocked countries and taxable checks get run.
    """

    user_client, basket = user_client_and_basket

    mocked_bcc, mocked_tcc = [
        basket_add_hook_steps["check_blocked_countries"],
        basket_add_hook_steps["check_taxable"],
    ]

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

    mock_basket_add_hook_steps(mocker, exceptfor="check_blocked_countries")

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

    mock_basket_add_hook_steps(mocker, exceptfor="check_blocked_countries")

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

    mock_basket_add_hook_steps(mocker, exceptfor="check_taxable")

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


def test_basket_add_webhook(mocker, user_client_and_basket):
    """Test that the pre-sale webhook gets triggered."""

    user_client, basket = user_client_and_basket

    mocked_notify = mocker.patch("payments.api.send_pre_sale_webhook")

    with reversion.create_revision():
        product = ProductFactory.create(system=basket.integrated_system)

    url = reverse(
        "v0:create_from_product", args=[basket.integrated_system.slug, product.sku]
    )
    resp = user_client.post(url)

    assert resp.status_code == 201
    mocked_notify.assert_called_once()
