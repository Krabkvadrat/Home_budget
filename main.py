import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils import executor
import datetime
from settings import TOKEN, CATEGORIES

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("gdrive_creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Budva expenses for bot").sheet1  # Open the sheet you want to work with

# Telegram bot setup
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


# State to store user data temporarily
user_data = {}

# Buttons for payment type
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("CASH 💵"), KeyboardButton("CARD 💳"))


# Start command handler
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_data[message.from_user.id] = {'step': 'payment_type'}  # Initialize the user's state
    await message.reply("Choose payment type:", reply_markup=keyboard)

# Payment type handler
@dp.message_handler(lambda message: message.text in ["CASH 💵", "CARD 💳"])
async def handle_payment_type(message: types.Message):
    user_data[message.from_user.id]['payment_type'] = message.text.split()[0]
    user_data[message.from_user.id]['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
    user_data[message.from_user.id]['year_month'] = datetime.datetime.now().strftime("%Y-%m")
    user_data[message.from_user.id]['step'] = 'value'  # Move to the next step
    await message.reply("Enter the value (amount):")


# Value handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'value')
async def handle_value(message: types.Message):
    try:
        # Convert the input to a float
        value = float(message.text)

        # Store the valid value in user_data
        user_data[message.from_user.id]['value'] = value
        user_data[message.from_user.id]['step'] = 'description'  # Move to the next step
        await message.reply("Enter the description:")
    except ValueError:
        # Handle the case where the input is not a valid float
        await message.reply("Please enter a valid number (e.g., 12.34):")


# Description handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'description')
async def handle_description(message: types.Message):
    user_data[message.from_user.id]['description'] = message.text
    user_data[message.from_user.id]['step'] = 'category'  # Move to the next step
    category_buttons = ReplyKeyboardMarkup(resize_keyboard=True)

    # Add buttons in groups of 3
    row = []
    for category in CATEGORIES:
        row.append(KeyboardButton(category.capitalize()))
        if len(row) == 3:  # If we have 4 buttons in the row, add the row to the keyboard
            category_buttons.add(*row)
            row = []  # Reset the row for the next group
    # If there are any remaining buttons in the last row, add them as well
    if row:
        category_buttons.add(*row)

    await message.reply("Choose a category:", reply_markup=category_buttons)


# Category handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'category')
async def handle_category(message: types.Message):
    # Debugging: print user's input and expected categories
    #print(f"User input: {message.text}, Available categories: {CATEGORIES}")

    # Check if the chosen category is valid
    if message.text in (category for category in CATEGORIES):
        user_data[message.from_user.id]['category'] = message.text
        user_data[message.from_user.id]['step'] = 'confirmation'  # Move to the confirmation step

        # Display confirmation
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
        await message.reply(confirmation_text, reply_markup=ReplyKeyboardRemove())
    else:
        await message.reply("Invalid category. Please choose a valid category.")


# Confirmation handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'confirmation' and message.text.lower() in ['yes', 'no'])
async def handle_confirmation(message: types.Message):
    if message.text.lower() == 'yes':
        # Append data to Google Sheet
        data = user_data[message.from_user.id]
        username = message.from_user.username if message.from_user.username else "No username"  # Handle case if the user has no username

        # Append the entire row, including username
        sheet.append_row([
            data['date'],
            data['value'],
            data['description'],
            data['category'],
            data['payment_type'],
            data['year_month'],
            username  # Adding username to the row
        ])
        await message.reply("Expense recorded!")
    else:
        await message.reply("Let's try again. Choose payment type:", reply_markup=keyboard)

    # Reset the user data
    user_data[message.from_user.id] = {'step': 'payment_type'}

# Run bot
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)