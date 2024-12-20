from django.core.management.base import BaseCommand

from system_meta.models import Product
from system_meta.tasks import update_products


class Command(BaseCommand):
    """
    A management command to update image_metadata for all Product objects
    Example usage: python manage.py update_product_image_data --product_id 1
    """

    help = "Update image_metadata for all Product objects"

    def add_arguments(self, parser):
        parser.add_argument(
            "--product-id",
            type=int,
            help="The ID of the product to update",
        )
        parser.add_argument(
            "--sku",
            type=str,
            help="The SKU of the product to update",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="The name of the product to update",
        )
        parser.add_argument(
            "--system-name",
            type=str,
            help="The system name of the product to update",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        product_id = kwargs.get("product_id")
        sku = kwargs.get("sku")
        name = kwargs.get("name")
        system_name = kwargs.get("system_name")

        if product_id:
            products = Product.objects.filter(id=product_id)
        elif sku:
            products = Product.objects.filter(sku=sku, system__name=system_name)
        elif name:
            products = Product.objects.filter(name=name)
        else:
            products = Product.objects.all()

        for product in products:
            update_products.delay(product.id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated image metadata for product {product.id}"
                )
            )
