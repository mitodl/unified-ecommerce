from payments.api import update_discount_codes
from payments.models import Discount
from unified_ecommerce.constants import DISCOUNT_TYPES, REDEMPTION_TYPES


class Command(BaseCommand):
    """
    Updates one or multiple discount codes using the Discount IDs.
    """

    help = "Updates one or multiple discount codes using the Discount IDs."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "discount_ids",
            type=int,
            nargs="+",
            help="The IDs of the discounts to update.",
        )

        parser.add_argument(
            "--expires",
            type=str,
            help="Optional expiration date for the code, in ISO-8601 (YYYY-MM-DD) format.",
        )

        parser.add_argument(
            "--activates",
            type=str,
            help="Optional activation date for the code, in ISO-8601 (YYYY-MM-DD) format.",
        )

        parser.add_argument(
            "--discount-type",
            type=str,
            help="Sets the discount type (dollars-off, percent-off, fixed-price; default percent-off)",
            default="dollars-off",
        )

        parser.add_argument(
            "--payment-type",
            type=str,
            help="Sets the payment type (marketing, sales, financial-assistance, customer-support, staff)",
            required=True,
        )

        parser.add_argument(
            "--amount",
            type=str,
            nargs="?",
            help="Sets the discount amount",
            required=True,
        )

        parser.add_argument(
            "--count",
            type=int,
            nargs="?",
            help="Number of codes to produce",
            default=1,
            required=True,
        )

        parser.add_argument(
            "--one-time",
            help="Make the resulting code(s) one-time redemptions (otherwise, default to unlimited)",
            action="store_true",
        )

        parser.add_argument(
            "--once-per-user",
            help="Make the resulting code(s) one-time per user redemptions (otherwise, default to unlimited)",
            action="store_true",
        )

        parser.add_argument(
            "--integrated-system",
            help="Integrated system ID or slug to associate with the discount.",
        )

        parser.add_argument(
            "--product",
            help="Product ID or SKU to associate with the discount.",
        )

        parser.add_argument(
            "--users",
            help="List of user IDs or emails to associate with the discount.",
        )

    def handle(self, *args, **options) -> None:
        updated_codes = []
        try:
            updated_codes = update_discount_codes(**options)
        except Exception as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(e))

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {updated_codes.count()} discounts.")
        )
