from django.core.management import BaseCommand

from payments.models import Discount


class Command(BaseCommand):
    """
    Deletes multiple discounts using the Discount IDs.
    An example usage of this command: python manage.py delete_discount_code 1 2 3
    """

    help = "Deletes multiple discounts using the Discount IDs."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "discount_ids",
            type=int,
            nargs="+",
            help="The IDs of the discounts to delete.",
        )

    def handle(self, *args, **options) -> None:
        discount_ids = options["discount_ids"]
        discounts = Discount.objects.filter(id__in=discount_ids)
        count, _ = discounts.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully deleted {count} discounts.")
        )
