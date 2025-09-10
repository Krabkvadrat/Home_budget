import gspread
import logging
import time
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

class GoogleSheetsError(Exception):
    pass

class Database:
    def __init__(self):
        self.workbook, self.expense_sheet, self.income_sheet = self._setup_google_sheets()

    def _setup_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("gdrive_creds.json", scope)
            client = gspread.authorize(creds)
            workbook = client.open("Budva expenses for bot")
            
            # Get the expense sheet (original sheet1)
            expense_sheet = workbook.sheet1
            
            # Get or create the income sheet
            try:
                income_sheet = workbook.worksheet("income")
                logger.info("Found existing income sheet")
            except gspread.WorksheetNotFound:
                logger.info("Creating new income sheet")
                income_sheet = workbook.add_worksheet(title="income", rows="1000", cols="20")
                # Add headers to the income sheet
                headers = ['date', 'value', 'description', 'type', 'payment_type', 'year_month', 'user']
                income_sheet.append_row(headers)
                logger.info("Income sheet created with headers")
            
            logger.info("Successfully connected to Google Sheets")
            return workbook, expense_sheet, income_sheet
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {str(e)}")
            raise GoogleSheetsError(f"Failed to connect to Google Sheets: {str(e)}")

    # Expense sheet methods (backward compatibility)
    def get_all_rows(self):
        """Get all rows from the expense sheet."""
        return self.expense_sheet.get_all_values()

    def get_last_rows(self, count=3):
        """Get the last N rows from the expense sheet."""
        return self.expense_sheet.get_all_values()[-count:]

    def append_row(self, row_data):
        """Append a new row to the expense sheet."""
        try:
            self.expense_sheet.append_row(row_data)
            logger.info("Successfully appended new expense row")
            return True
        except Exception as e:
            logger.error(f"Failed to append expense row: {str(e)}")
            raise GoogleSheetsError(f"Failed to append expense row: {str(e)}")

    def delete_row(self, row_index):
        """Delete a row from the expense sheet."""
        try:
            self.expense_sheet.delete_rows(row_index)
            logger.info(f"Successfully deleted expense row {row_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete expense row: {str(e)}")
            raise GoogleSheetsError(f"Failed to delete expense row: {str(e)}")

    # Income sheet methods
    def get_all_income_rows(self):
        """Get all rows from the income sheet."""
        return self.income_sheet.get_all_values()

    def get_last_income_rows(self, count=3):
        """Get the last N rows from the income sheet."""
        return self.income_sheet.get_all_values()[-count:]

    def append_income_row(self, row_data):
        """Append a new row to the income sheet."""
        try:
            self.income_sheet.append_row(row_data)
            logger.info("Successfully appended new income row")
            return True
        except Exception as e:
            logger.error(f"Failed to append income row: {str(e)}")
            raise GoogleSheetsError(f"Failed to append income row: {str(e)}")

    def delete_income_row(self, row_index):
        """Delete a row from the income sheet."""
        try:
            self.income_sheet.delete_rows(row_index)
            logger.info(f"Successfully deleted income row {row_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete income row: {str(e)}")
            raise GoogleSheetsError(f"Failed to delete income row: {str(e)}")

# Initialize database with retry mechanism
def init_database():
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            return Database()
        except GoogleSheetsError as e:
            if attempt == MAX_RETRIES - 1:
                raise
            logger.warning(f"Retry {attempt + 1}/{MAX_RETRIES} connecting to Google Sheets")
            time.sleep(2 ** attempt)  # Exponential backoff 