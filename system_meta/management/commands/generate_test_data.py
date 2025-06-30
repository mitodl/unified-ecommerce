"""
Adds some test data to the system. This includes three IntegratedSystems with three
products each.

Ignoring A003 because "help" is valid for argparse.
Ignoring S311 because it's complaining about the faker package.
"""
# ruff: noqa: S311

import random
import uuid
from decimal import Decimal

import faker
import reversion
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from django.db import transaction
from django.urls import reverse

from system_meta.models import IntegratedSystem, Product


def get_input(text):
    """Wrap the internal input function so we can test it later."""

    return input(text)


def fake_courseware_id(courseware_type: str, **kwargs) -> str:
    """
    Generate a fake courseware id.

    Courseware IDs generally are in the format:
    <type>-v1:<school ID>+<courseware ID>(+<run tag>)

    Type is either "course" or "program", depending on what you specify. School ID is
    one of "MITx", "MITxT", "edX", "xPRO", or "Sample". Courseware ID is a set of
    numbers: a number < 100, a number < 1000 with a leading zero, and an optional
    number < 10, separated by periods. Courseware ID is followed by an "x". This
    should be pretty like the IDs that are on MITx Online now (but pretty unlike the
    xPRO ones, which usually use a text courseware ID, but that's fine since these
    are fake).

    Arguments:
    - courseware_type (str): "course" or "program"; the type of
      courseware id to generate.

    Keyword Arguments:
    - include_run_tag (bool): include the run tag. Defaults to False.

    Returns:
    - str: The generated courseware id, in the normal format.
    """
    fake = faker.Faker()

    school_id = random.choice(["MITx", "MITxT", "edX", "xPRO", "Sample"])
    courseware_id = f"{random.randint(0, 99)}.{random.randint(0, 999):03d}"
    courseware_type = courseware_type.lower()
    optional_third_digit = random.randint(0, 9) if fake.boolean() else ""
    optional_run_tag = (
        f"+{random.randint(1, 3)}T{fake.date_this_decade().year}"
        if kwargs.get("include_run_tag", False)
        else ""
    )

    return (
        f"{courseware_type}-v1:{school_id}+{courseware_id}"
        f"{optional_third_digit}x{optional_run_tag}"
    )


class Command(BaseCommand):
    """Adds some test data to the system."""

    def add_arguments(self, parser: CommandParser) -> None:
        """Add arguments to the command parser."""
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Remove the test data. This is potentially dangerous.",
        )

        parser.add_argument(
            "--only-systems",
            action="store_true",
            help="Only add test systems. Will add two active and one inactive system.",
        )

        parser.add_argument(
            "--only-products",
            action="store_true",
            help="Only add test products.",
        )

        parser.add_argument(
            "--system-slug",
            type=str,
            help=(
                "The slug of the system to add products to."
                " Only used with --only-products."
            ),
            nargs="?",
        )

    def add_test_systems(self) -> None:
        """Add the test systems."""
        max_systems = 3
        for i in range(1, max_systems + 1):
            system = IntegratedSystem.objects.create(
                name=f"Test System {i}",
                description=f"Test System {i} description.",
                api_key=uuid.uuid4(),
            )
            system.payment_process_redirect_url = reverse(
                "cart", kwargs={"system_slug": system.slug}
            )
            system.save()

            self.stdout.write(f"Created system {system.name} - {system.slug}")

    def add_test_products(self, system_slug: str) -> None:
        """Add the test products to the specified system."""
        self.stdout.write(f"Creating test products for {system_slug}")

        if not IntegratedSystem.objects.filter(slug=system_slug).exists():
            self.stdout.write(
                self.style.ERROR(f"Integrated system {system_slug} does not exist.")
            )
            return

        system = IntegratedSystem.objects.get(slug=system_slug)

        max_products = 3
        with reversion.create_revision():
            for i in range(1, max_products + 1):
                product_sku = fake_courseware_id("course", include_run_tag=True)
                product = Product.objects.create(
                    name=f"Test Product {i}",
                    description=f"Test Product {i} description.",
                    sku=product_sku,
                    system=system,
                    price=Decimal(random.uniform(0, 999)).quantize(Decimal("0.01")),
                    system_data={
                        "courserun": product_sku,
                        "program": fake_courseware_id("program"),
                    },
                )
                self.stdout.write(f"Created product {product.id} - {product.sku}")

    def remove_test_data(self) -> None:
        """Remove the test data."""

        test_systems = (
            IntegratedSystem.all_objects.prefetch_related("products")
            .filter(name__startswith="Test System")
            .all()
        )

        self.stdout.write(
            self.style.WARNING("This command will remove these systems and products:")
        )

        for system in test_systems:
            self.stdout.write(
                self.style.WARNING(f"System: {system.name} ({system.id})")
            )

            for product in system.products.all():
                self.stdout.write(
                    self.style.WARNING(f"\tProduct: {product.name} ({product.id})")
                )

        self.stdout.write(
            self.style.WARNING(
                "This will ACTUALLY DELETE these records."
                " Are you sure you want to do this?"
            )
        )

        if get_input("Type 'yes' to continue: ") != "yes":
            self.stdout.write(self.style.ERROR("Aborting."))
            return

        with transaction.atomic():
            for system in test_systems:
                all_products = Product.all_objects.filter(
                    pk__in=[product.id for product in system.products.all()]
                )

                for product in all_products.all():
                    versions = (
                        reversion.models.Version.objects.get_for_object_reference(
                            Product, product.id
                        )
                    )
                    [version.revision.delete() for version in versions.all()]
                    versions.delete()

                all_products.delete()

        with transaction.atomic():
            IntegratedSystem.all_objects.filter(pk__in=test_systems).delete()

        self.stdout.write(self.style.SUCCESS("Test data removed."))

    def handle(self, *args, **options) -> None:  # noqa: ARG002
        """Handle the command."""
        remove = options["remove"]
        only_systems = options["only_systems"]
        only_products = options["only_products"]
        systems = []

        if remove:
            self.remove_test_data()
            return

        with transaction.atomic():
            if not only_products:
                self.add_test_systems()
                systems = [
                    system.slug
                    for system in (
                        IntegratedSystem.all_objects.filter(
                            name__startswith="Test System"
                        ).all()
                    )
                ]

            if only_systems:
                IntegratedSystem.objects.filter(
                    name__startswith="Test System"
                ).last().delete()
                return

            if only_products:
                if not options["system_slug"] or len(options["system_slug"]) == 0:
                    self.stdout.write(
                        self.style.ERROR(
                            "You must specify a system when using --only-products."
                        )
                    )
                    return
                else:
                    systems = [options["system_slug"]]

            self.stdout.write(f"we are creating products now {systems}")

            [self.add_test_products(system) for system in systems]

            if not only_products:
                IntegratedSystem.objects.filter(
                    name__startswith="Test System"
                ).last().delete()

            return
