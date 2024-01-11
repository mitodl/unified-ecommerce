"""
Adds a new integrated system to the application. This allows a system to access data
tied to it through the API.

Ignoring A003 because "help" is valid for argparse.
"""
# ruff: noqa: A003

from django.core.management import BaseCommand
from mitol.common.utils.datetime import now_in_utc

from system_meta.models import IntegratedSystem


class Command(BaseCommand):
    """
    Adds a new integrated system to the app.
    """

    help = "Adds a new integrated system to the app."

    def add_arguments(self, parser):
        """Parse arguments provided to the command."""

        parser.add_argument(
            "system_name",
            type=str,
            help="The name of the system to add.",
        )

        parser.add_argument(
            "--description",
            "-d",
            nargs="?",
            type=str,
            help="The system's description.",
            metavar="description",
        )

        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate the system after creation.",
        )

    def handle(self, **options) -> None:
        """Handle the command."""

        name = options["system_name"]
        description = options["description"]
        deactivate = options["deactivate"]

        if IntegratedSystem.objects.filter(name=name).exists():
            self.stdout.write(
                self.style.ERROR(f"Integrated system {name} already exists.")
            )
            return 1

        system = IntegratedSystem.objects.create(
            name=name,
            description=description,
            is_active=now_in_utc() if deactivate else None,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created integrated system {system.name}.")
        )

        return 0
