from django.core.management.base import BaseCommand
from system_meta.models import Product

class Command(BaseCommand):
    """
    A management command to update image_metadata for all Product objects
    Example usage: python manage.py update_product_image_data --id 1
    """

    help = "Update image_metadata for all Product objects"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--id",
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

    def handle(self, *args, **kwargs):
        id = kwargs.get("id")
        sku = kwargs.get("sku")
        name = kwargs.get("name")

        if id:
            products = Product.objects.filter(id=id)
        elif sku:
            products = Product.objects.filter(sku=sku)
        elif name:
            products = Product.objects.filter(name=name)
        else:
            products = Product.objects.all()

        for product in products:
            product.save()
            self.stdout.write(self.style.SUCCESS(f"Updated image_metadata for product {product}"))