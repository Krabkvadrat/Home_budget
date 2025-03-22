import gspread
import traceback
import io
import pandas as pd
import matplotlib.pyplot as plt
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils import executor
import datetime
import logging
import time
from settings import CATEGORIES
from credentials import TOKEN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Custom exceptions
class GoogleSheetsError(Exception):
    pass

class ValidationError(Exception):
    pass

# Google Sheets setup with retry mechanism
def setup_google_sheets():
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

# Initialize Google Sheets with retry
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        sheet = setup_google_sheets()
        break
    except GoogleSheetsError as e:
        if attempt == MAX_RETRIES - 1:
            raise
        logger.warning(f"Retry {attempt + 1}/{MAX_RETRIES} connecting to Google Sheets")
        time.sleep(2 ** attempt)  # Exponential backoff

# Telegram bot setup
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# State to store user data temporarily
user_data = {}

# Constants
MAX_VALUE = 10000000  # Maximum allowed value for expenses
MAX_DESCRIPTION_LENGTH = 200  # Maximum length for description

# Input validation functions
def validate_value(value: str) -> float:
    try:
        num_value = float(value)
        if num_value <= 0 or num_value > MAX_VALUE:
            raise ValidationError(f"Value must be between 0 and {MAX_VALUE}")
        return num_value
    except ValueError:
        raise ValidationError("Please enter a valid number")

def validate_description(description: str) -> str:
    if not description.strip():
        raise ValidationError("Description cannot be empty")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(f"Description cannot be longer than {MAX_DESCRIPTION_LENGTH} characters")
    return description.strip()

# Buttons for payment type
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("RUB 🇷🇺"), KeyboardButton("RSD 🇷🇸"))
keyboard.add(KeyboardButton("Show Last 3 Entries 📜"), KeyboardButton("Show analytics 📊"))
keyboard.add(KeyboardButton("Delete last row 🗑️"))

# Start command handler
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        user_data[message.from_user.id] = {'step': 'payment_type'}
        logger.info(f"User {message.from_user.id} started the bot")
        await message.reply("Hello, let's start!", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in start handler: {str(e)}")
        await message.reply("Sorry, something went wrong. Please try again later.")

# Payment type handler
@dp.message_handler(lambda message: message.text in ["RUB 🇷🇺", "RSD 🇷🇸"])
async def handle_payment_type(message: types.Message):
    try:
        user_data[message.from_user.id]['payment_type'] = message.text.split()[0]
        user_data[message.from_user.id]['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
        user_data[message.from_user.id]['year_month'] = datetime.datetime.now().strftime("%Y-%m")
        user_data[message.from_user.id]['step'] = 'value'
        logger.info(f"User {message.from_user.id} selected payment type: {message.text}")
        await message.reply("Enter the value (amount):")
    except KeyError:
        logger.warning(f"User {message.from_user.id} tried to use payment type without starting the bot")
        await message.reply("Please use /start command first")
    except Exception as e:
        logger.error(f"Error in payment type handler: {str(e)}")
        await message.reply("Sorry, something went wrong. Please try again later.")

# Value handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'value')
async def handle_value(message: types.Message):
    try:
        value = validate_value(message.text)
        user_data[message.from_user.id]['value'] = value
        user_data[message.from_user.id]['step'] = 'description'
        logger.info(f"User {message.from_user.id} entered value: {value}")
        await message.reply("Enter the description:")
    except ValidationError as e:
        logger.warning(f"User {message.from_user.id} entered invalid value: {message.text}")
        await message.reply(str(e))
    except Exception as e:
        logger.error(f"Error in value handler: {str(e)}")
        await message.reply("Sorry, something went wrong. Please try again later.")

# Description handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'description')
async def handle_description(message: types.Message):
    try:
        description = validate_description(message.text)
        user_data[message.from_user.id]['description'] = description
        user_data[message.from_user.id]['step'] = 'category'
        logger.info(f"User {message.from_user.id} entered description: {description}")
        
        category_buttons = ReplyKeyboardMarkup(resize_keyboard=True)
        row = []
        for category in CATEGORIES:
            row.append(KeyboardButton(category.capitalize()))
            if len(row) == 3:
                category_buttons.add(*row)
                row = []
        if row:
            category_buttons.add(*row)
        
        await message.reply("Choose a category:", reply_markup=category_buttons)
    except ValidationError as e:
        logger.warning(f"User {message.from_user.id} entered invalid description: {message.text}")
        await message.reply(str(e))
    except Exception as e:
        logger.error(f"Error in description handler: {str(e)}")
        await message.reply("Sorry, something went wrong. Please try again later.")

# Category handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'category')
async def handle_category(message: types.Message):
    try:
        if message.text not in CATEGORIES:
            logger.warning(f"User {message.from_user.id} selected invalid category: {message.text}")
            await message.reply("Invalid category. Please choose a valid category.")
            return

        user_data[message.from_user.id]['category'] = message.text
        user_data[message.from_user.id]['step'] = 'confirmation'
        logger.info(f"User {message.from_user.id} selected category: {message.text}")

        data = user_data[message.from_user.id]
        confirmation_text = (
            f"Date: {data['date']}\n"
            f"Value: {data['value']}\n"
            f"Description: {data['description']}\n"
            f"Category: {data['category']}\n"
            f"Payment Type: {data['payment_type']}\n"
            f"Year/Month: {data['year_month']}\n"
            "Confirm? (Yes/No)"
        )

        confirmation_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        confirmation_keyboard.add(KeyboardButton("Yes"), KeyboardButton("No"))
        await message.reply(confirmation_text, reply_markup=confirmation_keyboard)
    except Exception as e:
        logger.error(f"Error in category handler: {str(e)}")
        await message.reply("Sorry, something went wrong. Please try again later.")

# Confirmation handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'confirmation' and message.text in ['Yes', 'No'])
async def handle_confirmation(message: types.Message):
    try:
        if message.text == 'Yes':
            data = user_data[message.from_user.id]
            username = message.from_user.username if message.from_user.username else "No username"
            
            try:
                sheet.append_row([
                    data['date'],
                    data['value'],
                    data['description'],
                    data['category'],
                    data['payment_type'],
                    data['year_month'],
                    username
                ])
                logger.info(f"User {message.from_user.id} successfully added new expense")
                await message.reply("✅ Expense recorded successfully!", reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Failed to append row to Google Sheets: {str(e)}")
                await message.reply("❌ Failed to record expense. Please try again later.", reply_markup=keyboard)
        else:
            logger.info(f"User {message.from_user.id} cancelled expense recording")
            await message.reply("Expense recording cancelled. Choose payment type:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in confirmation handler: {str(e)}")
        await message.reply("Sorry, something went wrong. Please try again later.", reply_markup=keyboard)
    finally:
        user_data[message.from_user.id] = {'step': 'payment_type'}

# Handler to show the last 3 entries from Google Sheet
@dp.message_handler(lambda message: message.text == "Show Last 3 Entries 📜")
async def show_last_three_entries(message: types.Message):
    try:
        last_rows = sheet.get_all_values()[-3:]
        if not last_rows:
            await message.reply("No entries found.", reply_markup=keyboard)
            return

        last_entries_text = "\n\n".join(
            f"📅 Date: {row[0]}\n"
            f"💰 Value: {row[1]}\n"
            f"📝 Description: {row[2]}\n"
            f"🏷️ Category: {row[3]}\n"
            f"💳 Payment Type: {row[4]}\n"
            f"📅 Year/Month: {row[5]}\n"
            f"👤 User: {row[6]}"
            for row in last_rows
        )
        logger.info(f"User {message.from_user.id} requested last 3 entries")
        await message.reply(f"📋 Last 3 entries:\n\n{last_entries_text}", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error showing last entries: {str(e)}")
        await message.reply("❌ Failed to fetch entries. Please try again later.", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Delete last row 🗑️")
async def delete_last_row_confirm(message: types.Message):
    try:
        all_rows = sheet.get_all_values()
        if not all_rows:
            await message.reply("No data to delete.", reply_markup=keyboard)
            return

        last_row = all_rows[-1]
        last_row_text = (
            f"📅 Date: {last_row[0]}\n"
            f"💰 Value: {last_row[1]}\n"
            f"📝 Description: {last_row[2]}\n"
            f"🏷️ Category: {last_row[3]}\n"
            f"💳 Payment Type: {last_row[4]}\n"
            f"📅 Year/Month: {last_row[5]}\n"
            f"👤 User: {last_row[6]}"
        )
        
        user_data[message.from_user.id]['step'] = 'delete_confirmation'
        user_data[message.from_user.id]['last_row_index'] = len(all_rows)
        logger.info(f"User {message.from_user.id} requested to delete last row")
        await message.reply(
            f"⚠️ Are you sure you want to delete this entry?\n\n{last_row_text}\n\nConfirm? (Yes/No)",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Error preparing row deletion: {str(e)}")
        await message.reply("❌ Failed to prepare deletion. Please try again later.", reply_markup=keyboard)

@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'delete_confirmation')
async def handle_delete_confirmation(message: types.Message):
    try:
        if message.text.lower() == 'yes':
            last_row_index = user_data[message.from_user.id].get('last_row_index')
            if last_row_index:
                sheet.delete_rows(last_row_index)
                logger.info(f"User {message.from_user.id} successfully deleted last row")
                await message.reply("✅ Last row deleted successfully!", reply_markup=keyboard)
            else:
                logger.warning(f"User {message.from_user.id} attempted to delete row but index was not found")
                await message.reply("❌ Could not find the last row to delete.", reply_markup=keyboard)
        else:
            logger.info(f"User {message.from_user.id} cancelled row deletion")
            await message.reply("Deletion cancelled.", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error deleting row: {str(e)}")
        await message.reply("❌ Failed to delete row. Please try again later.", reply_markup=keyboard)
    finally:
        user_data[message.from_user.id] = {'step': 'payment_type'}

@dp.message_handler(lambda message: message.text == "Show analytics 📊")
async def show_analytics(message: types.Message):
    try:
        data = sheet.get_all_values()
        if len(data) <= 1:  # Only header row
            await message.reply("No data available for analytics.", reply_markup=keyboard)
            return

        df = pd.DataFrame(data[1:], columns=data[0])
        df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        
        current_date = datetime.datetime.now()
        two_months_ago = current_date - pd.DateOffset(months=1)
        two_months_ago = pd.Timestamp(two_months_ago).to_period('M').to_timestamp()
        filtered_df = df[df['date'] >= two_months_ago]

        if filtered_df.empty:
            await message.reply("No data available for the last two months.", reply_markup=keyboard)
            return

        grouped = filtered_df.groupby(['year_month', 'category'], as_index=False)['value'].sum()
        grouped = grouped.sort_values(['year_month', 'value'], ascending=False)

        fig, axs = plt.subplots(1, 2, figsize=(12, 6))
        unique_months = grouped['year_month'].unique()

        for i, month in enumerate(unique_months):
            month_data = grouped[grouped['year_month'] == month]
            total_value = month_data['value'].sum()
            month_data['percentage'] = round((month_data['value'] / total_value) * 100, 2)
            total_row = pd.DataFrame([['Total', '', total_value, 100]], columns=month_data.columns)
            month_data = pd.concat([month_data, total_row], ignore_index=True)

            axs[i].axis('tight')
            axs[i].axis('off')
            table = axs[i].table(
                cellText=month_data.values,
                colLabels=month_data.columns,
                cellLoc='center',
                loc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.auto_set_column_width(col=list(range(len(month_data.columns))))

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300)
        buffer.seek(0)
        plt.close()

        logger.info(f"User {message.from_user.id} requested analytics")
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=buffer,
            caption="📊 Analytics for the last two months"
        )
        buffer.close()
    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        await message.reply("❌ Failed to generate analytics. Please try again later.", reply_markup=keyboard)

# Help command handler
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    help_text = (
        "🤖 *Budget Bot Help*\n\n"
        "Available commands:\n"
        "• /start - Start the bot\n"
        "• /help - Show this help message\n\n"
        "Features:\n"
        "• Add expenses in RUB or RSD\n"
        "• Categorize your expenses\n"
        "• View last 3 entries\n"
        "• View monthly analytics\n"
        "• Delete last entry\n\n"
        "Need more help? Contact the administrator."
    )
    await message.reply(help_text, parse_mode='Markdown', reply_markup=keyboard)

# Run bot
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.critical(f"Failed to start bot: {str(e)}")
        raise
