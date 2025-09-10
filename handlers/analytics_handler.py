import logging
import datetime
import io
import pandas as pd
import matplotlib.pyplot as plt
from aiogram import types
from settings import CATEGORIES
from utils import create_analytics_keyboard, create_category_keyboard, create_main_keyboard
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class AnalyticsHandler(BaseHandler):
    def _register_handlers(self):
        """Register analytics-related message handlers."""
        self.dp.register_message_handler(self.analytics_button, lambda m: m.text == "Show analytics 📊")
        self.dp.register_message_handler(self.back_button, lambda m: m.text == "Back 🔙")
        self.dp.register_message_handler(self.show_analytics_two_months, lambda m: m.text == "Two months 📅")
        self.dp.register_message_handler(self.single_category_chart, lambda m: m.text == "Single category chart 📊")
        self.dp.register_message_handler(
            self.handle_single_category_selection,
            lambda m: self.user_data.get(m.from_user.id, {}).get('step') == 'single_category_selection'
        )
        self.dp.register_message_handler(self.show_last_year_chart, lambda m: m.text == "Last year 🗓️")

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
                
                plt.style.use("dark_background")

                # Create the line chart
                plt.figure(figsize=(10, 6))
                plt.plot(monthly_data.index, monthly_data.values, marker='o', linestyle='-', 
                        linewidth=2.5, markersize=8, color='#00ffff', markerfacecolor='#00ffff', 
                        markeredgecolor='white', markeredgewidth=1.5)
                plt.title(f'📊 {message.text} Expenses - Last 12 Months ({currency})', 
                         fontsize=14, color='white', fontweight='bold')
                plt.xlabel('Month', fontsize=12, color='white')
                plt.ylabel('Amount', fontsize=12, color='white')
                plt.xticks(rotation=45, color='white')
                plt.yticks(color='white')
                plt.grid(True, alpha=0.3, color='white')
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

                plt.style.use("dark_background")

                # Create the line chart
                plt.figure(figsize=(12, 6))
                plt.plot(monthly_data.index, monthly_data.values, marker='o', linestyle='-', 
                        linewidth=2.5, markersize=8, color='#00ffff', markerfacecolor='#00ffff', 
                        markeredgecolor='white', markeredgewidth=1.5)
                
                # Customize the plot
                plt.title(f'📊 Total Expenses - Last 12 Months ({currency})', 
                         fontsize=14, color='white', fontweight='bold')
                plt.xlabel('Month', fontsize=12, color='white')
                plt.ylabel('Total Expenses', fontsize=12, color='white')
                plt.xticks(rotation=45, color='white')
                plt.yticks(color='white')
                plt.grid(True, linestyle='--', alpha=0.3, color='white')
                
                # Add value labels on top of points
                for i, v in enumerate(monthly_data.values):
                    plt.text(i, v, f'{v:.0f}', ha='center', va='bottom', fontsize=10, color='white')
                
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