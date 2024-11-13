from django.core.management import BaseCommand
from datetime import datetime

import pytz
from unified_ecommerce import settings

from payments.models import Discount


class Command(BaseCommand):
    """
    Deletes multiple discounts using the Discount codes.
    An example usage of this command: python manage.py delete_discount_code 1 2 3
    """

    help = "Deletes multiple discounts using the Discount codes."

    def add_arguments(self, parser) -> None:
        """
        Add arguments to the command parser.
        """
        parser.add_argument(
            "discount_codes",
            type=int,
            nargs="+",
            help="The codes of the discounts to delete.",
        )

    def handle(self, **options) -> None:
        """
        Handle the deactivation of discounts based on provided discount codes.
        """
        discount_codes = options["discount_codes"]
        discounts = Discount.objects.filter(discount_code__in=discount_codes)
        # set the expiration date to the current date
        for discount in discounts:
            discount.expiration_date = datetime.now(
                tz=pytz.timezone(settings.TIME_ZONE)
            ).strftime("%Y-%m-%d")
            discount.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Discount codes {discount_codes} have been successfully deactivated."
            )
        )
