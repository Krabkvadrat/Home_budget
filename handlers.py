import logging
from aiogram import types
from handlers import ExpenseHandler, AnalyticsHandler

logger = logging.getLogger(__name__)

class Handlers:
    def __init__(self, bot, dp, db):
        self.bot = bot
        self.dp = dp
        self.db = db
        self.expense_handler = ExpenseHandler(bot, dp, db)
        self.analytics_handler = AnalyticsHandler(bot, dp, db)
        self._register_handlers()

    def _register_handlers(self):
        """Register all message handlers."""
        self.expense_handler._register_handlers()
        self.analytics_handler._register_handlers()