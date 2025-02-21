"""Plugin for the Google Sheets integration."""

from mitol.google_sheets_refunds.hooks import RefundResult, hookimpl
from mitol.google_sheets_refunds.utils import RefundRequestRow


class GoogleSheetsRefundsPlugin:
    """Plugin for the Google Sheets integration."""

    @hookimpl(specname="refunds_process_request")
    def update_from_google_sheets_row(
        self, refund_request_row: RefundRequestRow
    ) -> RefundResult:
        """
        Process the refund request row from Google Sheets.

        Args:
        - refund_result (RefundResult): The result of the refund processing.

        Returns:
        - ResultType: The result of the update.
        """

        from refunds.api import process_gsheet_request_row

        return process_gsheet_request_row(refund_request_row)
