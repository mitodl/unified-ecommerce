"""Tests for the manage_product command"""

from io import StringIO

import faker
import pytest
from django.core.management import call_command

from system_meta.factories import IntegratedSystemFactory, ProductFactory
from system_meta.models import Product

pytestmark = pytest.mark.django_db
FAKE = faker.Factory.create()


def test_add_product():
    """Tests that add_product adds a product"""
    out = StringIO()

    system = IntegratedSystemFactory()

    params = [
        "add",
        "--name",
        "test_product",
        "--sku",
        "test_sku",
        "--system",
        system.name,
        "--price",
        "1.00",
        "--description",
        "test_description",
        "--system-data",
        FAKE.json(),
    ]

    call_command(
        "manage_product",
        *params,
        stdout=out,
    )
    assert "Successfully created product" in out.getvalue()

    created_product = Product.objects.get(sku="test_sku", system=system)
    assert created_product.sku == "test_sku"


def test_list_products():
    """Test that products are listed"""
    out = StringIO()

    system = IntegratedSystemFactory()
    ProductFactory.create_batch(3, system=system)

    call_command(
        "manage_product",
        "list",
        stdout=out,
    )

    assert "3 products found." in out.getvalue()


def test_update_product():
    """Test that products are updated."""

    out = StringIO()

    system = IntegratedSystemFactory()
    product = ProductFactory(system=system)

    params = [
        "update",
        "--sku",
        product.sku,
        "--system",
        system.name,
        "--price",
        "1.00",
        "--description",
        "test_description",
        "--system-data",
        FAKE.json(),
    ]

    call_command(
        "manage_product",
        *params,
        stdout=out,
    )

    assert "Successfully updated product" in out.getvalue()

    product.refresh_from_db()
    assert product.price == 1.00
    assert product.description == "test_description"


def test_deactivate_product():
    """Test that deactivating a product works"""

    out = StringIO()

    system = IntegratedSystemFactory()
    product = ProductFactory(system=system)

    params = [
        "remove",
        "--sku",
        product.sku,
        "--system",
        system.name,
    ]

    call_command(
        "manage_product",
        *params,
        stdout=out,
    )

    assert "Successfully deactivated product" in out.getvalue()

    product.refresh_from_db()
    assert product.is_active is not None


def test_display_product():
    """Test that displaying a product works"""

    out = StringIO()

    system = IntegratedSystemFactory()
    product = ProductFactory(system=system)

    params = [
        "display",
        "--sku",
        product.sku,
        "--system",
        system.name,
    ]

    call_command(
        "manage_product",
        *params,
        stdout=out,
    )

    assert product.sku in out.getvalue()
    assert product.name in out.getvalue()
