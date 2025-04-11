import logging
import datetime
import io
import pandas as pd
import matplotlib.pyplot as plt
import mplcyberpunk
from aiogram import types
from aiogram.types import ReplyKeyboardRemove
from settings import CATEGORIES, AUTHORIZED_USERS
from utils import (
    validate_value, validate_description, ValidationError,
    create_main_keyboard, create_category_keyboard, create_confirmation_keyboard,
    format_expense_entry, create_analytics_keyboard
)

logger = logging.getLogger(__name__)

plt.style.use("cyberpunk")

class Handlers:
    def __init__(self, bot, dp, db):
        self.bot = bot
        self.dp = dp
        self.db = db
        self.user_data = {}
        self._register_handlers()

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        return user_id in AUTHORIZED_USERS

    async def _handle_unauthorized(self, message: types.Message):
        """Handle unauthorized access attempts."""
        logger.warning(f"Unauthorized access attempt from user {message.from_user.id}")
        await message.reply(
            "⛔️ Sorry, you are not authorized to use this bot.\n"
            "Please contact the administrator for access."
        )

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
        self.dp.register_message_handler(self.analytics_button, lambda m: m.text == "Show analytics 📊")
        self.dp.register_message_handler(self.back_button, lambda m: m.text == "Back 🔙")
        self.dp.register_message_handler(self.show_analytics_two_months, lambda m: m.text == "Two months 📅")
        self.dp.register_message_handler(self.single_category_chart, lambda m: m.text == "Single category chart 📊")
        self.dp.register_message_handler(
            self.handle_single_category_selection,
            lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'single_category_selection'
        )
        self.dp.register_message_handler(self.show_last_year_chart, lambda m: m.text == "Last year 🗓️")
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

    async def analytics_button(self, message: types.Message):
        try:
            await message.reply(f"Available analytics:", reply_markup=create_analytics_keyboard())

        except Exception as e:
            logger.error(f"Error in analytics_button handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def back_button(self, message: types.Message):
        try:
            await message.reply(f"Options:", reply_markup=create_main_keyboard())

        except Exception as e:
            logger.error(f"Error in back_button handler: {str(e)}")
            await message.reply("Sorry, something went wrong. Please try again later.")

    async def handle_payment_type(self, message: types.Message):
        """Handle payment type selection."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            self.user_data[message.from_user.id]['payment_type'] = message.text.split()[0]
            self.user_data[message.from_user.id]['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
            self.user_data[message.from_user.id]['year_month'] = datetime.datetime.now().strftime("%Y-%m")
            self.user_data[message.from_user.id]['step'] = 'value'
            logger.info(f"Authorized user {message.from_user.id} selected payment type: {message.text}")
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

    async def show_analytics_two_months(self, message: types.Message):
        """Show expense analytics."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            data = self.db.get_all_rows()
            if len(data) <= 1:  # Only header row
                await message.reply("No data available for analytics.", reply_markup=create_main_keyboard())
                return

            df = pd.DataFrame(data[1:], columns=data[0])
            df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            
            current_date = datetime.datetime.now()
            three_months_ago = current_date - pd.DateOffset(months=2)
            three_months_ago = pd.Timestamp(three_months_ago).to_period('M').to_timestamp()
            filtered_df = df[df['date'] >= three_months_ago]

            if filtered_df.empty:
                await message.reply("No data available for the last two months.", reply_markup=create_main_keyboard())
                return

            # Create separate analytics for each currency
            for currency in ['RUB', 'RSD']:
                currency_df = filtered_df[filtered_df['payment_type'] == currency]
                if currency_df.empty:
                    continue

                grouped = currency_df.groupby(['year_month', 'category'], as_index=False)['value'].sum()
                grouped = grouped.sort_values(['year_month', 'value'], ascending=False)

                # Calculate % change to previous month
                pivot = grouped.pivot(index='category', columns='year_month', values='value')
                pivot = pivot.sort_index(axis=1)
                percent_change = pivot.pct_change(axis=1) * 100
                percent_change_long = percent_change.reset_index().melt(
                    id_vars='category', var_name='year_month', value_name='Δ, %'
                )
                grouped = grouped.merge(percent_change_long, on=['category', 'year_month'], how='left')
                grouped['Δ, %'] = grouped['Δ, %'].round(1)

                # Create figure with subplots for each month
                unique_months = grouped['year_month'].unique()
                fig, axs = plt.subplots(1, len(unique_months[:2]), figsize=(6 * len(unique_months[:2]), 6))
                if len(unique_months) == 1:
                    axs = [axs]  # Make axs iterable if there's only one month

                for i, month in enumerate(unique_months[:2]):
                    month_data = grouped[grouped['year_month'] == month]
                    total_value = month_data['value'].sum()
                    month_data['share, %'] = ((month_data['value'] / total_value) * 100).round(1)

                    # Add row for total
                    total_row = pd.DataFrame([['Total', '', total_value, '', 100, '']],
                                             columns=['year_month', 'category', 'value', 'Δ, %',
                                                      'share, %', 'dummy'])
                    month_data = pd.concat([month_data, total_row.drop(columns=['dummy'])], ignore_index=True)

                    # Define display order
                    display_columns = ['year_month', 'category', 'value', 'share, %', 'Δ, %']

                    axs[i].axis('tight')
                    axs[i].axis('off')
                    table = axs[i].table(
                        cellText=month_data[display_columns].values,
                        colLabels=display_columns,
                        cellLoc='center',
                        loc='center'
                    )
                    table.auto_set_font_size(False)
                    table.set_fontsize(9)
                    table.auto_set_column_width(col=list(range(len(display_columns))))

                plt.suptitle(f'📊 Analytics for {currency} - Last Two Months', fontsize=14)
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300)
                buffer.seek(0)
                plt.close()

                await self.bot.send_photo(
                    chat_id=message.chat.id,
                    photo=buffer,
                    caption=f"📊 Analytics for {currency} - Last Two Months"
                )
                buffer.close()

            logger.info(f"User {message.from_user.id} requested analytics")
        except Exception as e:
            logger.error(f"Error generating analytics: {str(e)}")
            await message.reply("❌ Failed to generate analytics. Please try again later.", reply_markup=create_main_keyboard())

    async def single_category_chart(self, message: types.Message):
        """Handle single category chart button press."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            self.user_data[message.from_user.id] = {'step': 'single_category_selection'}
            await message.reply("Choose a category to view its chart:", reply_markup=create_category_keyboard())
        except Exception as e:
            logger.error(f"Error in single category chart handler: {str(e)}")
            await message.reply("❌ Failed to process request. Please try again later.", reply_markup=create_main_keyboard())

    async def handle_single_category_selection(self, message: types.Message):
        """Handle category selection for single category chart."""
        try:
            if message.text not in CATEGORIES:
                logger.warning(f"User {message.from_user.id} selected invalid category: {message.text}")
                await message.reply("Invalid category. Please choose a valid category.")
                return

            data = self.db.get_all_rows()
            if len(data) <= 1:  # Only header row
                await message.reply("No data available for analytics.", reply_markup=create_main_keyboard())
                return

            df = pd.DataFrame(data[1:], columns=data[0])
            df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            
            # Get data for the last 12 months
            current_date = datetime.datetime.now()
            twelve_months_ago = current_date - pd.DateOffset(months=12)
            filtered_df = df[df['date'] >= twelve_months_ago]

            if filtered_df.empty:
                await message.reply("No data available for the last 12 months.", reply_markup=create_main_keyboard())
                return

            # Create separate charts for each currency
            for currency in ['RUB', 'RSD']:
                currency_df = filtered_df[filtered_df['payment_type'] == currency]
                category_df = currency_df[currency_df['category'] == message.text]
                
                if category_df.empty:
                    continue

                # Group by month and sum values
                monthly_data = category_df.groupby(category_df['date'].dt.to_period('M'))['value'].sum()
                monthly_data.index = monthly_data.index.astype(str)

                # Create the line chart
                plt.figure(figsize=(10, 6))
                plt.plot(monthly_data.index, monthly_data.values, marker='o', linestyle='-')
                plt.title(f'📊 {message.text} Expenses - Last 12 Months ({currency})')
                plt.xlabel('Month')
                plt.ylabel('Amount')
                plt.xticks(rotation=45)
                plt.grid(True)
                plt.tight_layout()

                # Save the chart to a buffer
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300)
                buffer.seek(0)
                plt.close()

                await self.bot.send_photo(
                    chat_id=message.chat.id,
                    photo=buffer,
                    caption=f"📊 {message.text} Expenses - Last 12 Months ({currency})"
                )
                buffer.close()

            logger.info(f"User {message.from_user.id} requested single category chart for {message.text}")
            await message.reply("Choose another action:", reply_markup=create_analytics_keyboard())
        except Exception as e:
            logger.error(f"Error generating single category chart: {str(e)}")
            await message.reply("❌ Failed to generate chart. Please try again later.", reply_markup=create_main_keyboard())
        finally:
            self.user_data[message.from_user.id] = {'step': 'payment_type'}

    async def show_last_year_chart(self, message: types.Message):
        """Show line chart of total expenses for the last 12 months."""
        try:
            if not self._is_authorized(message.from_user.id):
                await self._handle_unauthorized(message)
                return

            data = self.db.get_all_rows()
            if len(data) <= 1:  # Only header row
                await message.reply("No data available for analytics.", reply_markup=create_main_keyboard())
                return

            df = pd.DataFrame(data[1:], columns=data[0])
            df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            
            # Get data for the last 12 months
            current_date = datetime.datetime.now()
            twelve_months_ago = current_date - pd.DateOffset(months=12)
            filtered_df = df[df['date'] >= twelve_months_ago]

            if filtered_df.empty:
                await message.reply("No data available for the last 12 months.", reply_markup=create_main_keyboard())
                return

            # Create separate charts for each currency
            for currency in ['RUB', 'RSD']:
                currency_df = filtered_df[filtered_df['payment_type'] == currency]
                if currency_df.empty:
                    continue

                # Group by month and sum values
                monthly_data = currency_df.groupby(currency_df['date'].dt.to_period('M'))['value'].sum()
                monthly_data.index = monthly_data.index.astype(str)

                # Create the line chart
                plt.figure(figsize=(12, 6))
                plt.plot(monthly_data.index, monthly_data.values, marker='o', linestyle='-', linewidth=2)
                
                # Customize the plot
                plt.title(f'📊 Total Expenses - Last 12 Months ({currency})', fontsize=14)
                plt.xlabel('Month', fontsize=12)
                plt.ylabel('Total Expenses', fontsize=12)
                plt.xticks(rotation=45)
                plt.grid(True, linestyle='--', alpha=0.7)
                
                # Add value labels on top of points
                for i, v in enumerate(monthly_data.values):
                    plt.text(i, v, f'{v:.0f}', ha='center', va='bottom', fontsize=10)
                
                plt.tight_layout()

                # Save the chart to a buffer
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300)
                buffer.seek(0)
                plt.close()

                await self.bot.send_photo(
                    chat_id=message.chat.id,
                    photo=buffer,
                    caption=f"📊 Total Expenses - Last 12 Months ({currency})"
                )
                buffer.close()

            # Show analytics keyboard after sending charts
            await message.reply(
                "Choose analytics type:",
                reply_markup=create_analytics_keyboard()
            )
            logger.info(f"User {message.from_user.id} requested last year chart")
        except Exception as e:
            logger.error(f"Error generating last year chart: {str(e)}")
            await message.reply("❌ Failed to generate chart. Please try again later.", reply_markup=create_main_keyboard())

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