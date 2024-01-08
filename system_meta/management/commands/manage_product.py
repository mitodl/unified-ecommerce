"""
Manages products within the app.
Ignoring A003 because "help" is valid for argparse.
"""
# ruff: noqa: A003, PLR0913, FBT002

from django.core.management import BaseCommand
from prettytable import PrettyTable

from system_meta.models import IntegratedSystem, Product


class Command(BaseCommand):
    """
    Manages products within the app.
    """

    help = "Manages products within the app."

    def add_arguments(self, parser):
        """Parse arguments provided to the command."""

        action_group = parser.add_argument_group(
            title="Action", description="Action to perform. Required."
        )
        action_group = action_group.add_mutually_exclusive_group(required=True)
        action_group.add_argument(
            "--add",
            "-a",
            action="store_true",
            help="Add a new product.",
        )
        action_group.add_argument(
            "--update",
            "-u",
            action="store_true",
            help="Update an existing product.",
        )
        action_group.add_argument(
            "--remove",
            "-r",
            action="store_true",
            help="Remove a product.",
        )
        action_group.add_argument(
            "--list",
            "-l",
            action="store_true",
            help="List all products.",
        )
        action_group.add_argument(
            "--display",
            "-d",
            action="store_true",
            help="Activate a product.",
        )

        crud_group = parser.add_argument_group(
            title="CRUD", description="Arguments for add, remove, and display."
        )
        crud_group.add_argument(
            "--sku",
            type=str,
            help="The product's SKU.",
            metavar="sku",
        )
        crud_group.add_argument(
            "--price",
            type=float,
            help="The product's price.",
            metavar="price",
        )
        crud_group.add_argument(
            "--name",
            "-n",
            type=str,
            help="The product's name.",
            metavar="name",
        )
        crud_group.add_argument(
            "--system",
            "-s",
            type=str,
            help="The system to add the product to.",
            metavar="system",
        )
        crud_group.add_argument(
            "--system-data",
            type=str,
            help="The system-specific data for the product.",
            metavar="system_data",
        )
        crud_group.add_argument(
            "--description",
            type=str,
            help="The product's description.",
            metavar="description",
        )
        crud_group.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate the product.",
        )

        parser.add_argument(
            "--activate",
            action="store_true",
            help="Activate the product. Only for Update.",
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
        except Product.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Product {sku} does not exist."))
            return

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
        return

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
            self.stdout.write(
                self.style.ERROR(
                    f"Product {sku} already exists in system {system_name}."
                )
            )
            return

        system = IntegratedSystem.objects.get(name=system_name)
        product = Product.objects.create(
            sku=sku,
            name=name,
            price=price,
            description=description,
            system=system,
            system_data=system_data,
            is_active=not deactivate,
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
        except Product.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Product {sku} does not exist."))
            return

        if price:
            product.price = price
        if name:
            product.name = name
        if description:
            product.description = description
        if system_data:
            product.system_data = system_data
        product.is_active = active

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
        except Product.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Product {sku} does not exist."))
            return

        product.is_active = False
        product.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deactivated product ID {product.id} - "
                f"{product.system.name} {product.sku}."
            )
        )

    def handle(self, **options) -> None:
        """Handle the command."""

        if options["list"]:
            self._list_products()
            return

        [sku, price, name, system_name, description, deactivate, system_data] = [
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

        if options["add"]:
            self._add_product(
                sku, price, name, system_name, description, deactivate, system_data
            )
            return

        if options["display"]:
            self._display_product(sku, system_name)
            return

        if options["remove"]:
            self._deactivate_product(sku, system_name)
            return

        if options["update"]:
            self._update_product(
                sku,
                system_name,
                price,
                name,
                description,
                system_data,
                options["activate"] and not deactivate,
            )
            return
