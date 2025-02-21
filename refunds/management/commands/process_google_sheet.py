"""Manually run the Google Sheets processing code."""

from django.core.management import BaseCommand

from refunds.tasks import process_google_sheets_requests


class Command(BaseCommand):
    """Command to manually run the Google Sheets processing code."""

    help = "Manually run the Google Sheets processing code now."

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle the command."""
        process_google_sheets_requests()
