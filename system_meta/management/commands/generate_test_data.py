"""
Adds some test data to the system. This includes three IntegratedSystems with three
products each.

Ignoring A003 because "help" is valid for argparse.
Ignoring S311 because it's complaining about the faker package.
"""
# ruff: noqa: A003, S311

import random
import uuid
from decimal import Decimal

import faker
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from django.db import transaction

from system_meta.models import IntegratedSystem, Product


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
        f"+{random.randint(1,3)}T{fake.date_this_decade().year}"
        if kwargs["include_run_tag"]
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
            help="Only add test systems.",
        )

        parser.add_argument(
            "--only-products",
            action="store_true",
            help="Only add test products.",
        )

        parser.add_argument(
            "--system",
            type=str,
            help=(
                "The name of the system to add products to."
                " Only used with --only-products."
            ),
            nargs="?",
        )

    def add_test_systems(self) -> None:
        """Add the test systems."""
        max_systems = 3
        for i in range(1, max_systems + 1):
            IntegratedSystem.objects.create(
                name=f"Test System {i}",
                description=f"Test System {i} description.",
                is_active=True,
                api_key=uuid.uuid4(),
            )

    def add_test_products(self, system: str) -> None:
        """Add the test products to the specified system."""

        if not IntegratedSystem.objects.filter(name=system).exists():
            self.stdout.write(
                self.style.ERROR(f"Integrated system {system} does not exist.")
            )
            return

        system = IntegratedSystem.objects.get(name=system)

        for i in range(1, 4):
            product_sku = fake_courseware_id("course", include_run_tag=True)
            Product.objects.create(
                name=f"Test Product {i}",
                description=f"Test Product {i} description.",
                sku=product_sku,
                system=system,
                is_active=True,
                price=Decimal(random.random() * 10000).quantize(Decimal("0.01")),
                system_data={
                    "courserun": product_sku,
                    "program": fake_courseware_id("program"),
                },
            )

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

        if input("Type 'yes' to continue: ") != "yes":
            self.stdout.write(self.style.ERROR("Aborting."))
            return

        for system in test_systems:
            Product.all_objects.filter(
                pk__in=[product.id for product in system.products.all()]
            ).delete()
            IntegratedSystem.all_objects.filter(pk=system.id).delete()

        self.stdout.write(self.style.SUCCESS("Test data removed."))

    def handle(self, *args, **options) -> None:  # noqa: ARG002
        """Handle the command."""
        remove = options["remove"]
        only_systems = options["only_systems"]
        only_products = options["only_products"]
        systems = [options["system"]] if options["system"] else []

        with transaction.atomic():
            if remove:
                self.remove_test_data()
                return

            if not only_products:
                self.add_test_systems()

            if not only_systems:
                if only_products and len(systems) == 0:
                    self.stdout.write(
                        self.style.ERROR(
                            "You must specify a system when using --only-products."
                        )
                    )
                    return
                else:
                    systems = [
                        system.name
                        for system in (
                            IntegratedSystem.all_objects.filter(
                                name__startswith="Test System"
                            ).all()
                        )
                    ]

                [self.add_test_products(system) for system in systems]
                return

            if not only_products:
                third_test_system = IntegratedSystem.all_objects.filter(
                    name__startswith="Test System"
                ).get()
                third_test_system.is_active = False
                third_test_system.save(update_fields=("is_active",))
