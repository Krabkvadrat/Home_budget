import logging
import datetime
from aiogram import types
from aiogram.types import ReplyKeyboardRemove
from settings import CATEGORIES
from utils import (
    validate_value, validate_description, ValidationError,
    create_main_keyboard, create_category_keyboard, create_confirmation_keyboard,
    format_expense_entry, create_income_menu_keyboard
)
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class ExpenseHandler(BaseHandler):
    def _register_handlers(self):
        """Register expense-related message handlers."""
        self.dp.register_message_handler(self.start, commands=['start'])
        self.dp.register_message_handler(self.handle_payment_type, 
                                       lambda m: m.text in ["RUB 🇷🇺", "RSD 🇷🇸"] and not self.user_data.get(m.from_user.id, {}).get('in_income_menu', False))
        self.dp.register_message_handler(self.handle_value, lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'value')
        self.dp.register_message_handler(self.handle_description, lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'description')
        self.dp.register_message_handler(self.handle_category, lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'category')
        self.dp.register_message_handler(
            self.handle_confirmation,
            lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'confirmation' and m.text in ['Yes', 'No']
        )
        self.dp.register_message_handler(self.show_last_three_entries, lambda m: m.text == "Show Last 3 Entries 📜")
        self.dp.register_message_handler(self.delete_last_row_confirm, lambda m: m.text == "Delete last row 🗑️")
        self.dp.register_message_handler(
            self.handle_delete_confirmation,
            lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'delete_confirmation'
        )
        self.dp.register_message_handler(self.handle_income_menu, lambda m: m.text == "Income menu 💰")
        self.dp.register_message_handler(self.help_command, commands=['help'])

    async def start(self, message: types.Message):
        """Handle /start command."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            self.user_data[message.from_user.id] = {'step': 'payment_type'}
            logger.info(f"Authorized user {message.from_user.id} started the bot")
            await message.reply("Hello, let's start!", reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error in start handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_payment_type(self, message: types.Message):
        """Handle payment type selection."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            payment_type = "RUB" if "RUB" in message.text else "RSD"
            self.user_data[message.from_user.id] = {
                'payment_type': payment_type,
                'date': datetime.datetime.now().strftime("%Y-%m-%d"),
                'year_month': datetime.datetime.now().strftime("%Y-%m"),
                'step': 'value'
            }
            logger.info(f"Authorized user {message.from_user.id} selected payment type: {payment_type}")
            await message.reply(f"You selected {payment_type}. Now enter the expense amount:", 
                              reply_markup=ReplyKeyboardRemove())
        except KeyError:
            logger.warning(f"User {message.from_user.id} tried to use payment type without starting the bot")
            await message.reply("Please use /start command first")
        except Exception as e:
            logger.error(f"Error in payment type handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_value(self, message: types.Message):
        """Handle expense value input."""
        try:
            value = validate_value(message.text)
            self.user_data[message.from_user.id]['value'] = value
            self.user_data[message.from_user.id]['step'] = 'description'
            logger.info(f"User {message.from_user.id} entered value: {value}")
            await message.reply("Enter the description:")
        except ValidationError as e:
            logger.warning(f"User {message.from_user.id} entered invalid value: {message.text}")
            await message.reply(str(e))
        except Exception as e:
            logger.error(f"Error in value handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_description(self, message: types.Message):
        """Handle expense description input."""
        try:
            description = validate_description(message.text)
            self.user_data[message.from_user.id]['description'] = description
            self.user_data[message.from_user.id]['step'] = 'category'
            logger.info(f"User {message.from_user.id} entered description: {description}")
            await message.reply("Choose a category:", reply_markup=create_category_keyboard())
        except ValidationError as e:
            logger.warning(f"User {message.from_user.id} entered invalid description: {message.text}")
            await message.reply(str(e))
        except Exception as e:
            logger.error(f"Error in description handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_category(self, message: types.Message):
        """Handle category selection."""
        try:
            if message.text not in CATEGORIES:
                logger.warning(f"User {message.from_user.id} selected invalid category: {message.text}")
                await message.reply("Invalid category. Please choose a valid category.")
                return

            self.user_data[message.from_user.id]['category'] = message.text
            self.user_data[message.from_user.id]['step'] = 'confirmation'
            logger.info(f"User {message.from_user.id} selected category: {message.text}")

            data = self.user_data[message.from_user.id]
            confirmation_text = (
                f"Date: {data['date']}\n"
                f"Value: {data['value']}\n"
                f"Description: {data['description']}\n"
                f"Category: {data['category']}\n"
                f"Payment Type: {data['payment_type']}\n"
                f"Year/Month: {data['year_month']}\n"
                "Confirm? (Yes/No)"
            )

            await message.reply(confirmation_text, reply_markup=create_confirmation_keyboard())
        except Exception as e:
            logger.error(f"Error in category handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_confirmation(self, message: types.Message):
        """Handle expense confirmation."""
        try:
            if message.text == 'Yes':
                data = self.user_data[message.from_user.id]
                username = message.from_user.username if message.from_user.username else "No username"
                
                try:
                    self.db.append_row([
                        data['date'],
                        data['value'],
                        data['description'],
                        data['category'],
                        data['payment_type'],
                        data['year_month'],
                        username
                    ])
                    logger.info(f"User {message.from_user.id} successfully added new expense")
                    await message.reply("✅ Expense recorded successfully!", reply_markup=create_main_keyboard())
                except Exception as e:
                    logger.error(f"Failed to append row to Google Sheets: {str(e)}")
                    await message.reply("❌ Failed to record expense. Please try again later.", reply_markup=create_main_keyboard())
            else:
                logger.info(f"User {message.from_user.id} cancelled expense recording")
                await message.reply("Expense recording cancelled. Choose payment type:", reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error in confirmation handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.", reply_markup=create_main_keyboard())
        finally:
            self.user_data[message.from_user.id] = {'step': 'payment_type'}

    async def show_last_three_entries(self, message: types.Message):
        """Show last 3 expense entries."""
        try:
            last_rows = self.db.get_last_rows()
            if not last_rows:
                await message.reply("No entries found.", reply_markup=create_main_keyboard())
                return

            last_entries_text = "\n\n".join(format_expense_entry(row) for row in last_rows)
            logger.info(f"User {message.from_user.id} requested last 3 entries")
            await message.reply(f"📋 Last 3 entries:\n\n{last_entries_text}", reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error showing last entries: {str(e)}")
            await message.reply("❌ Failed to fetch entries. Please try again later.", reply_markup=create_main_keyboard())

    async def delete_last_row_confirm(self, message: types.Message):
        """Confirm deletion of last row."""
        try:
            all_rows = self.db.get_all_rows()
            if not all_rows:
                await message.reply("No data to delete.", reply_markup=create_main_keyboard())
                return

            last_row = all_rows[-1]
            last_row_text = format_expense_entry(last_row)
            
            self.user_data[message.from_user.id]['step'] = 'delete_confirmation'
            self.user_data[message.from_user.id]['last_row_index'] = len(all_rows)
            logger.info(f"User {message.from_user.id} requested to delete last row")
            await message.reply(
                f"⚠️ Are you sure you want to delete this entry?\n\n{last_row_text}\n\nConfirm? (Yes/No)",
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            logger.error(f"Error preparing row deletion: {str(e)}")
            await message.reply("❌ Failed to prepare deletion. Please try again later.", reply_markup=create_main_keyboard())

    async def handle_delete_confirmation(self, message: types.Message):
        """Handle deletion confirmation."""
        try:
            if message.text.lower() == 'yes':
                last_row_index = self.user_data[message.from_user.id].get('last_row_index')
                if last_row_index:
                    self.db.delete_row(last_row_index)
                    logger.info(f"User {message.from_user.id} successfully deleted last row")
                    await message.reply("✅ Last row deleted successfully!", reply_markup=create_main_keyboard())
                else:
                    logger.warning(f"User {message.from_user.id} attempted to delete row but index was not found")
                    await message.reply("❌ Could not find the last row to delete.", reply_markup=create_main_keyboard())
            else:
                logger.info(f"User {message.from_user.id} cancelled row deletion")
                await message.reply("Deletion cancelled.", reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error deleting row: {str(e)}")
            await message.reply("❌ Failed to delete row. Please try again later.", reply_markup=create_main_keyboard())
        finally:
            self.user_data[message.from_user.id] = {'step': 'payment_type'}

    async def handle_income_menu(self, message: types.Message):
        """Handle income menu button press."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            # Set flag to indicate user is in income menu
            self.user_data[message.from_user.id] = {'in_income_menu': True}
            await message.reply("💰 Income Menu - Choose an option:", 
                              reply_markup=create_income_menu_keyboard())
        except Exception as e:
            logger.error(f"Error in income menu handler: {str(e)}")
            await message.reply("❌ Failed to open income menu. Please try again.", 
                              reply_markup=create_main_keyboard())

    async def help_command(self, message: types.Message):
        """Show help message."""
        if not self._is_authorized(message.from_user.id):
            await self._handle_unauthorized(message)
            return

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
        await message.reply(help_text, parse_mode='Markdown', reply_markup=create_main_keyboard()) 