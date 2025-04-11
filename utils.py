import logging
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from settings import CATEGORIES

logger = logging.getLogger(__name__)

# Constants
MAX_VALUE = 10000000  # Maximum allowed value for expenses
MAX_DESCRIPTION_LENGTH = 200  # Maximum length for description

class ValidationError(Exception):
    pass

def validate_value(value: str) -> float:
    """Validate and convert expense value."""
    try:
        num_value = float(value)
        if num_value <= 0 or num_value > MAX_VALUE:
            raise ValidationError(f"Value must be between 0 and {MAX_VALUE}")
        return num_value
    except ValueError:
        raise ValidationError("Please enter a valid number")

def validate_description(description: str) -> str:
    """Validate expense description."""
    if not description.strip():
        raise ValidationError("Description cannot be empty")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(f"Description cannot be longer than {MAX_DESCRIPTION_LENGTH} characters")
    return description.strip()

def create_main_keyboard():
    """Create the main keyboard with all available options."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("RUB 🇷🇺"), KeyboardButton("RSD 🇷🇸"))
    keyboard.add(KeyboardButton("Show Last 3 Entries 📜"), KeyboardButton("Show analytics 📊"))
    keyboard.add(KeyboardButton("Delete last row 🗑️"))
    return keyboard

def create_analytics_keyboard():
    """Create the main keyboard with all available options."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Two months 📅"), KeyboardButton("Last year 🗓️"))
    keyboard.add(KeyboardButton("Single category chart 📊"))
    keyboard.add(KeyboardButton("Back 🔙"))
    return keyboard

def create_category_keyboard():
    """Create keyboard with category buttons."""
    category_buttons = ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for category in CATEGORIES:
        row.append(KeyboardButton(category.capitalize()))
        if len(row) == 3:
            category_buttons.add(*row)
            row = []
    if row:
        category_buttons.add(*row)
    return category_buttons

def create_confirmation_keyboard():
    """Create keyboard with Yes/No buttons."""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Yes"), KeyboardButton("No"))
    return keyboard

def format_expense_entry(row):
    """Format a single expense entry for display."""
    return (
        f"📅 Date: {row[0]}\n"
        f"💰 Value: {row[1]}\n"
        f"📝 Description: {row[2]}\n"
        f"🏷️ Category: {row[3]}\n"
        f"💳 Payment Type: {row[4]}\n"
        f"📅 Year/Month: {row[5]}\n"
        f"👤 User: {row[6]}"
    ) 