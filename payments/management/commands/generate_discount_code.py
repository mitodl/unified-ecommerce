import csv

from django.core.management import BaseCommand

from payments.api import generate_discount_code


class Command(BaseCommand):
    """
    Generates discount codes.
    An example usage of this command:
    python manage.py generate_discount_code --payment-type marketing \
    --amount 10 --count 5 --one-time
    """

    help = "Generates discount codes."

    def add_arguments(self, parser) -> None:
        """
        Add command line arguments to the parser.
        """
        parser.add_argument(
            "--prefix",
            type=str,
            help="The prefix to use for the codes. (Maximum length 13 characters)",
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
            default="dollars-off",
        )

        parser.add_argument(
            "--payment-type",
            type=str,
            help=(
                "Sets the payment type (marketing, sales, financial-assistance, "
                "customer-support, staff)"
            ),
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
            "codes",
            nargs="*",
            type=str,
            help="Discount codes to generate (ignored if --count is specified)",
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

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        """
        Handle the generation of discount codes based on the provided arguments.
        """
        # Don't allow the creation of bulk unlimited discounts.
        if not kwargs.get("one_time") and kwargs.get("bulk"):
            self.stderr.write(
                self.style.ERROR(
                    "Bulk discounts must be one-time redemptions. "
                    "Please specify the --one-time flag."
                )
            )
            return

        generated_codes = []
        try:
            generated_codes = generate_discount_code(**kwargs)
        except (ValueError, TypeError) as e:
            self.stderr.write(self.style.ERROR(e))

        with open("generated-codes.csv", mode="w") as output_file:  # noqa: PTH123
            writer = csv.DictWriter(
                output_file, ["code", "type", "amount", "expiration_date"]
            )

            writer.writeheader()

            for code in generated_codes:
                writer.writerow(
                    {
                        "code": code.discount_code,
                        "type": code.discount_type,
                        "amount": code.amount,
                        "expiration_date": code.expiration_date,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"{len(generated_codes)} created."))
