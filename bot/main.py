"""Main bot application."""
import logging
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)
from telegram.request import HTTPXRequest

from bot.config import Config
from bot.database.database import db
from bot.handlers.commands import (
    start_command,
    help_command,
    status_command,
    cancel_command,
    avatars_command,
    voices_command
)
from bot.handlers.conversation import (
    generate_command,
    receive_avatar_id,
    receive_voice_id,
    receive_text,
    cancel_conversation,
    handle_regular_message,
    AVATAR_ID,
    VOICE_ID,
    TEXT_INPUT
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Initialize database after bot starts."""
    logger.info("Initializing database...")
    await db.init_db()
    logger.info("Database initialized successfully")

    # Set bot commands menu
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("generate", "Создать видео"),
        BotCommand("avatars", "Список моих аватаров"),
        BotCommand("voices", "Список доступных голосов"),
        BotCommand("status", "Проверить статус генерации"),
        BotCommand("cancel", "Отменить генерацию"),
        BotCommand("help", "Показать справку"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu set successfully")


async def error_handler(update: object, context):
    """Handle errors in the bot."""
    logger.error(f"Exception while handling an update: {context.error}")

    # Notify user - wrapped in try-except to prevent cascading failures
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка при обработке вашего запроса. Попробуйте позже."
            )
        except Exception as e:
            # If we can't send error message, just log it
            logger.error(f"Failed to send error message to user: {e}")


def main():
    """Run the bot."""
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validated successfully")

        # Configure request with increased timeouts for large file uploads
        # Video files can be large (HD 1920x1080), so we need generous timeouts
        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=120.0,   # 2 minutes for reading
            write_timeout=300.0,  # 5 minutes for uploading large video files
            pool_timeout=30.0
        )

        # Create application
        application = (
            Application.builder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .request(request)
            .post_init(post_init)
            .build()
        )

        # Add conversation handler for video generation
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('generate', generate_command)],
            states={
                AVATAR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_avatar_id)],
                VOICE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_voice_id)],
                TEXT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
            },
            fallbacks=[CommandHandler('cancel', cancel_conversation)],
        )

        application.add_handler(conv_handler)

        # Add command handlers
        application.add_handler(CommandHandler('start', start_command))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('status', status_command))
        application.add_handler(CommandHandler('cancel', cancel_command))
        application.add_handler(CommandHandler('avatars', avatars_command))
        application.add_handler(CommandHandler('voices', voices_command))

        # Add message handler for regular messages
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_regular_message)
        )

        # Add error handler
        application.add_error_handler(error_handler)

        # Start bot
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
