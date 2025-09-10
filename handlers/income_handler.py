import logging
import datetime
from aiogram import types
from aiogram.types import ReplyKeyboardRemove
from settings import INCOME_TYPES
from utils import (
    validate_value, validate_description, ValidationError,
    create_main_keyboard, create_income_type_keyboard, create_confirmation_keyboard,
    format_income_entry, create_income_menu_keyboard
)
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class IncomeHandler(BaseHandler):
    def _register_handlers(self):
        """Register income-related message handlers."""
        self.dp.register_message_handler(self.handle_income_currency_selection, 
                                       lambda m: m.text in ["Income RUB 🇷🇺", "Income RSD 🇷🇸"])
        self.dp.register_message_handler(self.handle_income_value, 
                                       lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'income_value')
        self.dp.register_message_handler(self.handle_income_description, 
                                       lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'income_description')
        self.dp.register_message_handler(self.handle_income_type, 
                                       lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'income_type')
        self.dp.register_message_handler(
            self.handle_income_confirmation,
            lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'income_confirmation' and m.text in ['Yes', 'No']
        )
        self.dp.register_message_handler(self.show_last_three_income_entries, lambda m: m.text == "Show Last 3 Income Entries 📜")
        self.dp.register_message_handler(self.delete_last_income_row_confirm, lambda m: m.text == "Delete last income row 🗑️")
        self.dp.register_message_handler(
            self.handle_income_delete_confirmation,
            lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'income_delete_confirmation'
        )
        self.dp.register_message_handler(self.handle_back_to_main, lambda m: m.text == "Back to Main 🔙")

    async def handle_income_currency_selection(self, message: types.Message):
        """Handle income currency selection from income menu."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            payment_type = "RUB" if "RUB" in message.text else "RSD"
            self.user_data[message.from_user.id] = {
                'payment_type': payment_type,
                'step': 'income_value'
            }
            
            await message.reply(
                f"💰 You selected {payment_type}. Now enter the income amount:",
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            logger.error(f"Error in income currency selection handler: {str(e)}")
            await message.reply("❌ Failed to process currency selection. Please try again.", 
                              reply_markup=create_income_menu_keyboard())

    async def handle_income_value(self, message: types.Message):
        """Handle income value input."""
        try:
            value = validate_value(message.text)
            self.user_data[message.from_user.id]['value'] = value
            self.user_data[message.from_user.id]['step'] = 'income_description'
            
            await message.reply(
                f"💰 Amount: {value} {self.user_data[message.from_user.id]['payment_type']}\n"
                f"Now enter a description for this income:",
                reply_markup=ReplyKeyboardRemove()
            )
        except ValidationError as e:
            await message.reply(f"❌ {str(e)}\nPlease enter a valid amount:")
        except Exception as e:
            logger.error(f"Error in income value handler: {str(e)}")
            await message.reply("❌ Failed to process income amount. Please try again.", 
                              reply_markup=create_main_keyboard())

    async def handle_income_description(self, message: types.Message):
        """Handle income description input."""
        try:
            description = validate_description(message.text)
            self.user_data[message.from_user.id]['description'] = description
            self.user_data[message.from_user.id]['step'] = 'income_type'
            
            await message.reply(
                f"📝 Description: {description}\n"
                f"Now select the income type:",
                reply_markup=create_income_type_keyboard()
            )
        except ValidationError as e:
            await message.reply(f"❌ {str(e)}\nPlease enter a valid description:")
        except Exception as e:
            logger.error(f"Error in income description handler: {str(e)}")
            await message.reply("❌ Failed to process description. Please try again.", 
                              reply_markup=create_main_keyboard())

    async def handle_income_type(self, message: types.Message):
        """Handle income type selection."""
        try:
            if message.text not in INCOME_TYPES:
                logger.warning(f"User {message.from_user.id} selected invalid income type: {message.text}")
                await message.reply("❌ Invalid income type. Please choose a valid type.")
                return

            user_data = self.user_data[message.from_user.id]
            user_data['type'] = message.text
            user_data['step'] = 'income_confirmation'

            # Show confirmation
            confirmation_text = (
                f"💰 Please confirm your income entry:\n\n"
                f"📅 Date: {datetime.date.today()}\n"
                f"💰 Amount: {user_data['value']} {user_data['payment_type']}\n"
                f"📝 Description: {user_data['description']}\n"
                f"🏷️ Type: {user_data['type']}\n"
                f"👤 User: {message.from_user.username or message.from_user.first_name}\n\n"
                f"Is this correct?"
            )
            
            await message.reply(confirmation_text, reply_markup=create_confirmation_keyboard())
        except Exception as e:
            logger.error(f"Error in income type handler: {str(e)}")
            await message.reply("❌ Failed to process income type. Please try again.", 
                              reply_markup=create_main_keyboard())

    async def handle_income_confirmation(self, message: types.Message):
        """Handle income confirmation."""
        try:
            if message.text == "Yes":
                user_data = self.user_data[message.from_user.id]
                current_date = datetime.date.today()
                year_month = current_date.strftime("%Y-%m")
                
                # Prepare data for Google Sheets
                row_data = [
                    current_date.strftime("%Y-%m-%d"),  # date
                    str(user_data['value']),            # value
                    user_data['description'],            # description
                    user_data['type'],                   # type
                    user_data['payment_type'],           # payment_type
                    year_month,                          # year_month
                    message.from_user.username or message.from_user.first_name  # user
                ]
                
                # Save to Google Sheets
                if self.db.append_income_row(row_data):
                    await message.reply(
                        f"✅ Income entry saved successfully!\n"
                        f"💰 {user_data['value']} {user_data['payment_type']} - {user_data['description']}",
                        reply_markup=create_income_menu_keyboard()
                    )
                    logger.info(f"User {message.from_user.id} added income: {user_data['value']} {user_data['payment_type']}")
                else:
                    await message.reply("❌ Failed to save income entry. Please try again.", 
                                      reply_markup=create_income_menu_keyboard())
            else:
                await message.reply("❌ Income entry cancelled.", reply_markup=create_income_menu_keyboard())
            
            # Reset user data
            self.user_data[message.from_user.id] = {}
        except Exception as e:
            logger.error(f"Error in income confirmation handler: {str(e)}")
            await message.reply("❌ Failed to process confirmation. Please try again.", 
                              reply_markup=create_income_menu_keyboard())

    async def show_last_three_income_entries(self, message: types.Message):
        """Show last 3 income entries."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            data = self.db.get_all_income_rows()
            if len(data) <= 1:  # Only header row
                await message.reply("💰 No income entries found.", reply_markup=create_income_menu_keyboard())
                return

            last_entries = data[-3:]  # Get last 3 entries
            
            response = "💰 **Last 3 Income Entries:**\n\n"
            for i, entry in enumerate(reversed(last_entries), 1):
                response += f"**Entry {i}:**\n{format_income_entry(entry)}\n\n"
            
            await message.reply(response, reply_markup=create_income_menu_keyboard())
            logger.info(f"User {message.from_user.id} requested last 3 income entries")
        except Exception as e:
            logger.error(f"Error showing last income entries: {str(e)}")
            await message.reply("❌ Failed to retrieve income entries. Please try again later.", 
                              reply_markup=create_income_menu_keyboard())

    async def delete_last_income_row_confirm(self, message: types.Message):
        """Confirm deletion of last income row."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            data = self.db.get_all_income_rows()
            if len(data) <= 1:  # Only header row
                await message.reply("💰 No income entries to delete.", reply_markup=create_income_menu_keyboard())
                return

            last_entry = data[-1]
            self.user_data[message.from_user.id] = {'step': 'income_delete_confirmation'}
            
            confirmation_text = (
                f"🗑️ **Confirm Income Deletion**\n\n"
                f"Are you sure you want to delete this income entry?\n\n"
                f"{format_income_entry(last_entry)}"
            )
            
            await message.reply(confirmation_text, reply_markup=create_confirmation_keyboard())
        except Exception as e:
            logger.error(f"Error in delete income confirmation: {str(e)}")
            await message.reply("❌ Failed to process deletion request. Please try again later.", 
                              reply_markup=create_income_menu_keyboard())

    async def handle_income_delete_confirmation(self, message: types.Message):
        """Handle income deletion confirmation."""
        try:
            if message.text == "Yes":
                data = self.db.get_all_income_rows()
                if len(data) > 1:  # More than just header
                    last_row_index = len(data)
                    if self.db.delete_income_row(last_row_index):
                        await message.reply("✅ Last income entry deleted successfully!", 
                                          reply_markup=create_income_menu_keyboard())
                        logger.info(f"User {message.from_user.id} deleted last income entry")
                    else:
                        await message.reply("❌ Failed to delete income entry. Please try again later.", 
                                          reply_markup=create_income_menu_keyboard())
                else:
                    await message.reply("💰 No income entries to delete.", 
                                      reply_markup=create_income_menu_keyboard())
            else:
                await message.reply("❌ Deletion cancelled.", reply_markup=create_income_menu_keyboard())
            
            # Reset user data
            self.user_data[message.from_user.id] = {}
        except Exception as e:
            logger.error(f"Error in income delete confirmation handler: {str(e)}")
            await message.reply("❌ Failed to process deletion. Please try again.", 
                              reply_markup=create_income_menu_keyboard())

    async def handle_back_to_main(self, message: types.Message):
        """Handle back to main menu."""
        try:
            self.user_data[message.from_user.id] = {'step': 'payment_type'}
            await message.reply("🏠 Back to main menu:", reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error in back to main handler: {str(e)}")
            await message.reply("❌ Failed to go back. Please try again.", reply_markup=create_main_keyboard())
