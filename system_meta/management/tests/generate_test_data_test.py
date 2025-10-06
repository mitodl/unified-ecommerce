"""Tests for the manage_product command"""

import re
from io import StringIO

import faker
import pytest
from django.core.management import call_command

from system_meta.factories import IntegratedSystemFactory, ProductFactory
from system_meta.management.commands.generate_test_data import fake_courseware_id
from system_meta.models import IntegratedSystem, Product

pytestmark = pytest.mark.django_db
FAKE = faker.Factory.create()


@pytest.mark.parametrize(
    ("include_run_tag", "program_or_course"),
    [(True, True), (True, False), (False, True), (False, False)],
)
def test_generate_fake_courseware_id(include_run_tag, program_or_course):
    """
    Tests that generate_fake_courseware_id generates a courseware id in the proper format.
    """

    courseware_id = fake_courseware_id(
        "program" if program_or_course else "course", include_run_tag=include_run_tag
    )

    assert (
        courseware_id.startswith("program-v1:")
        if program_or_course
        else courseware_id.startswith("course-v1:")
    )

    if program_or_course:
        if include_run_tag:
            courseware_re = re.compile(
                r"program-v1:(MITx|MITxT|edX|xPRO|Sample)\+\d{1,2}\.\d{3}\d?x\+\d{1,3}T\d{4}"
            )
        else:
            courseware_re = re.compile(
                r"program-v1:(MITx|MITxT|edX|xPRO|Sample)\+\d{1,2}\.\d{3}\d?x"
            )
    else:  # noqa: PLR5501
        if include_run_tag:
            courseware_re = re.compile(
                r"course-v1:(MITx|MITxT|edX|xPRO|Sample)\+\d{1,2}\.\d{3}\d?x\+\d{1,3}T\d{4}"
            )
        else:
            courseware_re = re.compile(
                r"course-v1:(MITx|MITxT|edX|xPRO|Sample)\+\d{1,2}\.\d{3}\d?x"
            )

    assert courseware_re.match(courseware_id)


def test_add_only_systems():
    """Test that only-systems adds test systems with no products."""
    out = StringIO()

    call_command("generate_test_data", only_systems=True, stdout=out)

    assert (
        IntegratedSystem.all_objects.filter(name__startswith="Test System").count() == 3
    )
    assert IntegratedSystem.objects.filter(name__startswith="Test System").count() == 2


@pytest.mark.parametrize("system_type", ["normal", "skip", "wrong"])
def test_add_only_products(system_type):
    """
    Test that only-product adds products for the specified system.

    Args:
    - system_type (str): type of system to try
      normal is make a system normally (i.e. run the command correctly)
      skip is don't make a system at all (should generate a specific error)
      wrong is make a system, but specify something incorrect
    """
    out = StringIO()

    if system_type == "skip":
        call_command("generate_test_data", only_products=True, stdout=out)

        assert "You must specify a system" in out.getvalue()
    elif system_type == "wrong":
        bad_slug = "some nonsense"
        call_command(
            "generate_test_data", only_products=True, system_slug=bad_slug, stdout=out
        )

        assert f"Integrated system {bad_slug} does not exist" in out.getvalue()
    else:
        system = IntegratedSystemFactory.create()

        call_command(
            "generate_test_data",
            only_products=True,
            system_slug=system.slug,
            stdout=out,
        )

        assert "Created product" in out.getvalue()

        assert (
            Product.objects.filter(
                name__startswith="Test Product", system=system
            ).count()
            == 3
        )


def test_add_all():
    """Test that just running the command generates expected output."""

    call_command("generate_test_data")

    assert (
        IntegratedSystem.all_objects.filter(name__startswith="Test System").count() == 3
    )
    assert IntegratedSystem.objects.filter(name__startswith="Test System").count() == 2

    for system in IntegratedSystem.all_objects.all():
        assert (
            Product.all_objects.filter(
                system=system, name__startswith="Test Product"
            ).count()
            == 3
        )


def test_remove_test_data(mocker):
    """Test that the remove test data command does the best it can to just remove test data."""

    input_mock = mocker.patch(
        "system_meta.management.commands.generate_test_data.get_input",
        return_value="yes",
    )
    out = StringIO()

    ProductFactory.create_batch(3)
    before_system_count = IntegratedSystem.all_objects.count()
    before_product_count = Product.all_objects.count()

    call_command("generate_test_data")

    assert before_system_count < IntegratedSystem.all_objects.count()
    assert before_product_count < Product.all_objects.count()

    call_command("generate_test_data", "--remove", stdout=out)

    assert "Test data removed" in out.getvalue()
    input_mock.assert_called()

    # Checking these two ways for a reason:
    # - Make sure the test data wasn't soft deleted
    # - Make sure it didn't soft-delete any of the products/systems we created

    assert IntegratedSystem.all_objects.count() == before_system_count
    assert Product.all_objects.count() == before_product_count
    assert IntegratedSystem.objects.count() == before_system_count
    assert Product.objects.count() == before_product_count
