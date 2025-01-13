"""
Manages products within the app.

Return codes:
0: Success
1: Product does not exist
2: Product already exists

Ignoring A003 because "help" is valid for argparse.
"""

# ruff: noqa: A003, PLR0913, FBT002
import argparse

from django.core.management import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc
from prettytable import PrettyTable

from system_meta.models import IntegratedSystem, Product


class Command(BaseCommand):
    """
    Manages products within the app.
    """

    help = "Manages products within the app."

    def add_arguments(self, parser):
        """Parse arguments provided to the command."""

        sku_system_args = argparse.ArgumentParser(add_help=False)
        sku_system_args.add_argument(
            "--sku",
            type=str,
            required=True,
            help="The product's SKU.",
            metavar="sku",
        )
        sku_system_args.add_argument(
            "--system",
            "-s",
            type=str,
            required=True,
            help="The system slug to add the product to.",
            metavar="system",
        )

        crud_args = argparse.ArgumentParser(add_help=False)
        crud_args.add_argument(
            "--name",
            "-n",
            type=str,
            help="The product's name.",
            metavar="name",
        )
        crud_args.add_argument(
            "--system-data",
            type=str,
            help="The system-specific data for the product.",
            metavar="system_data",
        )
        crud_args.add_argument(
            "--description",
            type=str,
            default="",
            help="The product's description.",
            metavar="description",
        )

        subparsers = parser.add_subparsers(dest="subcommand", required=True)

        add_cmd = subparsers.add_parser(
            "add",
            help="Add a new product.",
            parents=[sku_system_args, crud_args],
        )
        add_cmd.add_argument(
            "--deactivate",
            dest="is_active",
            default=True,
            action="store_true",
            help="Deactivate the product.",
        )
        add_cmd.add_argument(
            "--price",
            type=float,
            required=True,
            help="The product's price.",
            metavar="price",
        )

        update_cmd = subparsers.add_parser(
            "update",
            help="Update an existing product.",
            parents=[sku_system_args, crud_args],
        )
        update_cmd.add_argument(
            "--price",
            type=float,
            help="The product's price.",
            metavar="price",
        )

        is_active_args = update_cmd.add_mutually_exclusive_group()
        is_active_args.add_argument(
            "--deactivate",
            dest="is_active",
            action="store_false",
            help="Deactivate the product.",
        )
        is_active_args.add_argument(
            "--activate",
            dest="is_active",
            default=True,
            action="store_true",
            help="Activate the product.",
        )

        subparsers.add_parser(
            "remove",
            help="Remove a product.",
            parents=[sku_system_args],
        )

        subparsers.add_parser(
            "list",
            help="List all products.",
        )

        subparsers.add_parser(
            "display",
            help="Display a product.",
            parents=[sku_system_args],
        )

    def _list_products(self):
        """List all products."""

        products = Product.objects.all()
        table = PrettyTable()

        table.field_names = ["Active", "SKU", "System", "Description", "Price"]
        table.add_rows(
            [
                product.is_active,
                product.sku,
                product.system.name,
                product.description,
                product.price,
            ]
            for product in products
        )

        self.stdout.write(table.get_string())
        self.stdout.write(self.style.SUCCESS(f"{len(products)} products found."))

    def _display_product(self, sku, system_name):
        """Display a product."""

        try:
            product = Product.all_objects.get(sku=sku, system__name=system_name)
        except Product.DoesNotExist as err:
            exception_message = f"Product {sku} does not exist."
            raise CommandError(exception_message, returncode=1) from err

        table = PrettyTable()
        table.align = "l"
        table.header = False

        table.add_row(["ID", product.id])
        table.add_row(["Active", product.is_active])
        table.add_row(["SKU", product.sku])
        table.add_row(["Name", product.name])
        table.add_row(["System", product.system.name])
        table.add_row(["Description", product.description])
        table.add_row(["Price", product.price])
        table.add_row(["System Data", product.system_data])

        self.stdout.write(table.get_string())

    def _add_product(
        self,
        sku,
        price,
        name,
        system_name,
        description,
        deactivate=False,
        system_data=None,
    ):
        """Create a product."""

        if Product.objects.filter(sku=sku, system__name=system_name).exists():
            exception_message = "Product {sku} already exists in system {system_name}."
            raise CommandError(exception_message, returncode=2)

        system = IntegratedSystem.objects.get(slug=system_name)
        product = Product.objects.create(
            sku=sku,
            name=name,
            price=price,
            description=description,
            system=system,
            system_data=system_data,
            deleted_on=None if not deactivate else now_in_utc(),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created product ID {product.id} - "
                f"{product.system.name} {product.sku}."
            )
        )

    def _update_product(
        self,
        sku,
        system_name,
        price=None,
        name=None,
        description=None,
        system_data=None,
        active=False,
    ):
        """Update a product."""

        try:
            product = Product.all_objects.get(sku=sku, system__name=system_name)
        except Product.DoesNotExist as err:
            exception_message = f"Product {sku} does not exist."
            raise CommandError(exception_message, returncode=1) from err

        if price:
            product.price = price
        if name:
            product.name = name
        if description:
            product.description = description
        if system_data:
            product.system_data = system_data

        product.deleted_on = None if active else now_in_utc()

        product.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated product ID {product.id} - "
                f"{product.system.name} {product.sku}."
            )
        )

    def _deactivate_product(self, sku, system_name):
        """Deactivate a product."""

        try:
            product = Product.objects.get(sku=sku, system__name=system_name)
        except Product.DoesNotExist as err:
            exception_message = f"Product {sku} does not exist."
            raise CommandError(exception_message, returncode=1) from err

        product.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deactivated product ID {product.id} - "
                f"{product.system.name} {product.sku}."
            )
        )

    def handle(self, **options) -> None:
        """Handle the command."""

        subcommand = options["subcommand"]

        if subcommand == "list":
            self._list_products()
            return

        [sku, price, name, system_name, description, is_active, system_data] = [
            options.get(arg)
            for arg in [
                "sku",
                "price",
                "name",
                "system",
                "description",
                "deactivate",
                "system_data",
            ]
        ]

        if subcommand == "add":
            self._add_product(
                sku, price, name, system_name, description, is_active, system_data
            )
            return

        if subcommand == "display":
            self._display_product(sku, system_name)
            return

        if subcommand == "remove":
            self._deactivate_product(sku, system_name)
            return

        if subcommand == "update":
            self._update_product(
                sku,
                system_name,
                price,
                name,
                description,
                system_data,
                is_active,
            )
            return
