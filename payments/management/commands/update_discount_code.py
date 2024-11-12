from datetime import datetime

import pytz
from django.core.management import BaseCommand

from payments.api import update_discount_codes
from unified_ecommerce import settings


class Command(BaseCommand):
    """
    Updates one or multiple discount codes using the Discount IDs.
    example usage of this command:
    python manage.py update_discount_code 1 2 3 --expires 2023-01-01 --amount 10 \
    --discount-type dollars-off --payment-type marketing
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
            help=(
                "Optional expiration date for the code, "
                "in ISO-8601 (YYYY-MM-DD) format."
            ),
        )

        parser.add_argument(
            "--activates",
            type=str,
            help=(
                "Optional activation date for the code, "
                "in ISO-8601 (YYYY-MM-DD) format."
            ),
        )

        parser.add_argument(
            "--discount-type",
            type=str,
            help=(
                "Sets the discount type (dollars-off, percent-off, fixed-price; "
                "default percent-off)"
            ),
        )

        parser.add_argument(
            "--payment-type",
            type=str,
            help=(
                "Sets the payment type (marketing, sales, financial-assistance, "
                "customer-support, staff)"
            ),
        )

        parser.add_argument(
            "--amount",
            type=str,
            nargs="?",
            help="Sets the discount amount",
        )

        parser.add_argument(
            "--one-time",
            help=(
                "Make the resulting code(s) one-time redemptions "
                "(otherwise, default to unlimited)"
            ),
            action="store_true",
        )

        parser.add_argument(
            "--once-per-user",
            help=(
                "Make the resulting code(s) one-time per user redemptions "
                "(otherwise, default to unlimited)"
            ),
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

        parser.add_argument(
            "--expire-now",
            help="Expire the discount code(s) immediately.",
            action="store_true",
        )

    def handle(self, **options) -> None:
        """
        Handle the updating of discount codes based on the provided options.
        """
        if options.get("expire_now"):
            # convert date to string
            options["expires"] = datetime.now(
                tz=pytz.timezone(settings.TIME_ZONE)
            ).strftime("%Y-%m-%d")

        number_of_updated_codes = 0
        try:
            number_of_updated_codes = update_discount_codes(**options)
        except (ValueError, KeyError, TypeError) as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(e))

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {number_of_updated_codes} discounts."
            )
        )
