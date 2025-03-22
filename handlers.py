import logging
import datetime
import io
import pandas as pd
import matplotlib.pyplot as plt
from aiogram import types
from aiogram.types import ReplyKeyboardRemove
from settings import CATEGORIES
from utils import (
    validate_value, validate_description, ValidationError,
    create_main_keyboard, create_category_keyboard, create_confirmation_keyboard,
    format_expense_entry
)

logger = logging.getLogger(__name__)

class Handlers:
    def __init__(self, bot, dp, db):
        self.bot = bot
        self.dp = dp
        self.db = db
        self.user_data = {}
        self._register_handlers()

    def _register_handlers(self):
        """Register all message handlers."""
        self.dp.register_message_handler(self.start, commands=['start'])
        self.dp.register_message_handler(self.handle_payment_type, lambda m: m.text in ["RUB 🇷🇺", "RSD 🇷🇸"])
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
        self.dp.register_message_handler(self.show_analytics, lambda m: m.text == "Show analytics 📊")
        self.dp.register_message_handler(self.help_command, commands=['help'])

    async def start(self, message: types.Message):
        """Handle /start command."""
        try:
            self.user_data[message.from_user.id] = {'step': 'payment_type'}
            logger.info(f"User {message.from_user.id} started the bot")
            await message.reply("Hello, let's start!", reply_markup=create_main_keyboard())
        except Exception as e:
            logger.error(f"Error in start handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_payment_type(self, message: types.Message):
        """Handle payment type selection."""
        try:
            self.user_data[message.from_user.id]['payment_type'] = message.text.split()[0]
            self.user_data[message.from_user.id]['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
            self.user_data[message.from_user.id]['year_month'] = datetime.datetime.now().strftime("%Y-%m")
            self.user_data[message.from_user.id]['step'] = 'value'
            logger.info(f"User {message.from_user.id} selected payment type: {message.text}")
            await message.reply("Enter the value (amount):")
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

    async def show_analytics(self, message: types.Message):
        """Show expense analytics."""
        try:
            data = self.db.get_all_rows()
            if len(data) <= 1:  # Only header row
                await message.reply("No data available for analytics.", reply_markup=create_main_keyboard())
                return

            df = pd.DataFrame(data[1:], columns=data[0])
            df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            
            current_date = datetime.datetime.now()
            two_months_ago = current_date - pd.DateOffset(months=1)
            two_months_ago = pd.Timestamp(two_months_ago).to_period('M').to_timestamp()
            filtered_df = df[df['date'] >= two_months_ago]

            if filtered_df.empty:
                await message.reply("No data available for the last two months.", reply_markup=create_main_keyboard())
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
            await self.bot.send_photo(
                chat_id=message.chat.id,
                photo=buffer,
                caption="📊 Analytics for the last two months"
            )
            buffer.close()
        except Exception as e:
            logger.error(f"Error generating analytics: {str(e)}")
            await message.reply("❌ Failed to generate analytics. Please try again later.", reply_markup=create_main_keyboard())

    async def help_command(self, message: types.Message):
        """Show help message."""
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