import gspread
import logging
import time
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

class GoogleSheetsError(Exception):
    pass

class Database:
    def __init__(self):
        self.sheet = self._setup_google_sheets()

    def _setup_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("gdrive_creds.json", scope)
            client = gspread.authorize(creds)
            sheet = client.open("Budva expenses for bot").sheet1
            logger.info("Successfully connected to Google Sheets")
            return sheet
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {str(e)}")
            raise GoogleSheetsError(f"Failed to connect to Google Sheets: {str(e)}")

    def get_all_rows(self):
        """Get all rows from the sheet."""
        return self.sheet.get_all_values()

    def get_last_rows(self, count=3):
        """Get the last N rows from the sheet."""
        return self.sheet.get_all_values()[-count:]

    def append_row(self, row_data):
        """Append a new row to the sheet."""
        try:
            self.sheet.append_row(row_data)
            logger.info("Successfully appended new row")
            return True
        except Exception as e:
            logger.error(f"Failed to append row: {str(e)}")
            raise GoogleSheetsError(f"Failed to append row: {str(e)}")

    def delete_row(self, row_index):
        """Delete a row from the sheet."""
        try:
            self.sheet.delete_rows(row_index)
            logger.info(f"Successfully deleted row {row_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete row: {str(e)}")
            raise GoogleSheetsError(f"Failed to delete row: {str(e)}")

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