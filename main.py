import gspread
import io
import matplotlib.pyplot as plt
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton
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
keyboard.add(KeyboardButton("Show Last 3 Entries 📜"), KeyboardButton("Show analytics 📊"))
keyboard.add(KeyboardButton("Delete last row 🗑️"))

# Start command handler
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_data[message.from_user.id] = {'step': 'payment_type'}  # Initialize the user's state
    await message.reply("Hello, let's start!", reply_markup=keyboard)

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

        # Create regular keyboard with Yes and No buttons
        confirmation_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        yes_button = KeyboardButton("Yes")
        no_button = KeyboardButton("No")
        confirmation_keyboard.add(yes_button, no_button)

        await message.reply(confirmation_text, reply_markup=confirmation_keyboard)
    else:
        await message.reply("Invalid category. Please choose a valid category.")

# Confirmation handler
@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'confirmation' and message.text in ['Yes', 'No'])
async def handle_confirmation(message: types.Message):
    if message.text == 'Yes':
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
        await message.reply("Expense recorded!", reply_markup=keyboard)
    else:
        await message.reply("Let's try again. Choose payment type:", reply_markup=keyboard)

    # Reset the user data
    user_data[message.from_user.id] = {'step': 'payment_type'}

# Handler to show the last 3 entries from Google Sheet
@dp.message_handler(lambda message: message.text == "Show Last 3 Entries 📜")
async def show_last_three_entries(message: types.Message):
    # Fetch the last 3 rows from the sheet
    last_rows = sheet.get_all_values()[-3:]
    last_entries_text = "\n\n".join(
        f"Date: {row[0]}\nValue: {row[1]}\nDescription: {row[2]}\nCategory: {row[3]}\nPayment Type: {row[4]}\nYear/Month: {row[5]}\nUser: {row[6]}"
        for row in last_rows
    )

    # Send the formatted text to the user
    await message.reply(f"Last 3 entries:\n\n{last_entries_text}", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Delete last row 🗑️")
async def delete_last_row_confirm(message: types.Message):
    all_rows = sheet.get_all_values()  # Fetch all rows with data
    if len(all_rows) > 0:
        last_row = all_rows[-1]  # Fetch the last non-empty row
        last_row_text = ", ".join(last_row)
        user_data[message.from_user.id]['step'] = 'delete_confirmation'
        user_data[message.from_user.id]['last_row_index'] = len(all_rows)  # Store the index of the last row
        await message.reply(f"Are you sure you want to delete the last row?\n\n{last_row_text}\n\nConfirm? (Yes/No)", reply_markup=ReplyKeyboardRemove())
    else:
        await message.reply("No data to delete.")

@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).get('step') == 'delete_confirmation')
async def handle_delete_confirmation(message: types.Message):
    if message.text.lower() == 'yes':
        # Retrieve the index of the last non-empty row
        last_row_index = user_data[message.from_user.id].get('last_row_index')
        if last_row_index:
            sheet.delete_rows(last_row_index)  # Delete the last non-empty row
            await message.reply("Last row deleted!", reply_markup=keyboard)
        else:
            await message.reply("Could not find the last row to delete.", reply_markup=keyboard)
    else:
        await message.reply("Deletion canceled.", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "Show analytics 📊")
async def show_analytics(message: types.Message):
    # Get all rows from the sheet
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])  # Skip the header row

    # Parse the "Дата" column to datetime and filter the last 2 months
    df['Дата'] = pd.to_datetime(df['Дата'], format='%d.%m', errors='coerce')
    df = df.dropna(subset=['Дата'])  # Remove rows with invalid dates
    df['Дата'] = df['Дата'].apply(lambda x: x.replace(year=datetime.datetime.now().year))
    two_months_ago = datetime.datetime.now() - pd.DateOffset(months=2)
    filtered_df = df[df['Дата'] >= two_months_ago]

    # Group by "Категория" and calculate the total for each
    grouped = filtered_df.groupby('Категория')['Сумма'].sum().reset_index()

    # Create a table image
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis('tight')
    ax.axis('off')

    # Format the table as a matplotlib table
    table = ax.table(
        cellText=grouped.values,
        colLabels=grouped.columns,
        cellLoc='center',
        loc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(grouped.columns))))

    # Save the table as an image
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    plt.close()

    # Send the table image to the user
    await bot.send_photo(chat_id=message.chat.id, photo=buffer)
    buffer.close()


# Run bot
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)