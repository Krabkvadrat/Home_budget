import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.utils import executor
from credentials import TOKEN
from database import init_database
from handlers import Handlers

# Configure logging
LOG_DIR = "/app/logs"  # Docker-friendly path
os.makedirs(LOG_DIR, exist_ok=True)  # Create logs directory if it doesn't exist

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Initialize bot and dispatcher
        bot = Bot(token=TOKEN)
        dp = Dispatcher(bot)

        # Initialize database
        db = init_database()

        # Initialize handlers
        handlers = Handlers(bot, dp, db)

        # Start bot
        logger.info("Starting bot...")
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.critical(f"Failed to start bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()
