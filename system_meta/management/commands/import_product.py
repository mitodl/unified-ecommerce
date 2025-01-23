"""Import a product from the Learn API."""

import logging

from django.core.management.base import BaseCommand

from system_meta.api import get_product_metadata
from system_meta.models import IntegratedSystem, Product

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Import a product from the Learn API."""

    help = "Import a product from the Learn API."

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument(
            "system_slug",
            type=str,
            help="The slug of the system to import the product from",
        )

        parser.add_argument(
            "readable_id",
            type=str,
            help="The readable ID of the product to import",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Handle the command."""
        metadata = get_product_metadata(kwargs["system_slug"], kwargs["readable_id"])

        system = IntegratedSystem.objects.get(slug=kwargs["system_slug"])
        product = Product.objects.create(
            sku=metadata["sku"],
            name=metadata["title"],
            description=metadata["description"],
            image_metadata=metadata["image"],
            price=metadata["price"],
            system=system,
            details_url=metadata["url"],
        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported product {product}")
        )
