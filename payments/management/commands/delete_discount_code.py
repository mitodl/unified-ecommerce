from datetime import datetime

import pytz
from django.core.management import BaseCommand

from payments.models import BulkDiscountCollection, Discount
from unified_ecommerce import settings


class Command(BaseCommand):
    """
    Deactivates multiple discounts using the Discount codes.
    An example usage of this command:
    python manage.py delete_discount_code --discount_codes 1 2 3
    """

    help = "Deactivate multiple discounts using the Discount codes."

    def add_arguments(self, parser) -> None:
        """
        Add arguments to the command parser.
        """
        parser.add_argument(
            "--discount-codes",
            type=str,
            nargs="+",
            help="The codes of the discounts to deactivate.",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            help="The prefix of the codes to deactivate.",
        )

    def handle(self, **options) -> None:
        """
        Handle the deactivation of discounts based on provided discount codes.
        """
        if options["prefix"]:
            prefix = options["prefix"]
            bulk_discount_collection = BulkDiscountCollection.objects.filter(
                prefix=prefix
            ).first()
            if not bulk_discount_collection:
                error_message = (
                    f"Bulk discount collection with prefix {prefix} does not exist."
                )
                raise ValueError(error_message)
            discounts = bulk_discount_collection.discounts.all()
        else:
            discount_codes = options["discount_codes"]
            discounts = Discount.objects.filter(discount_code__in=discount_codes)
        # set the expiration date to the current date
        for discount in discounts:
            discount.expiration_date = datetime.now(
                tz=pytz.timezone(settings.TIME_ZONE)
            ).strftime("%Y-%m-%d")
            discount.save()
        self.stderr.write(
            self.style.SUCCESS("Discounts have been successfully deactivated.")
        )
