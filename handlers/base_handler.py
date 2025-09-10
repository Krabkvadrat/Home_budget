import logging
from aiogram import types
from settings import AUTHORIZED_USERS

logger = logging.getLogger(__name__)

class BaseHandler:
    def __init__(self, bot, dp, db):
        self.bot = bot
        self.dp = dp
        self.db = db
        self.user_data = {}

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
        """Register all message handlers. To be implemented by child classes."""
        raise NotImplementedError("Child classes must implement _register_handlers") 