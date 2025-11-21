"""Command handlers for the Telegram bot."""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.database.database import db
from bot.services.video_service import video_service

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user

    # Create user in database
    await db.get_or_create_user(user.id, user.username)

    welcome_message = (
        "👋 Привет! Я бот для генерации видео с помощью HeyGen.\n\n"
        "Я помогу создать видео с AI-аватаром, который озвучит ваш текст!\n\n"
        "📋 Для начала работы используйте команду /generate\n"
        "❓ Для помощи: /help"
    )

    await update.message.reply_text(welcome_message)
    logger.info(f"User {user.id} started the bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_message = (
        "📖 *Инструкция по использованию:*\n\n"
        "*Способ 1 - Пошаговый:*\n"
        "1️⃣ Используйте команду /generate\n"
        "2️⃣ Отправьте ID аватара (например: `avatar_123abc`)\n"
        "3️⃣ Отправьте ID голоса (например: `voice_456def`)\n"
        "4️⃣ Отправьте текст для озвучки\n\n"
        "*Способ 2 - Одним сообщением:*\n"
        "Отправьте все данные в формате:\n"
        "`avatar_123abc | voice_456def | Привет! Это мой текст.`\n\n"
        "*Доступные команды:*\n"
        "• /generate - создать видео\n"
        "• /status - проверить статус генерации\n"
        "• /cancel - отменить текущую генерацию\n"
        "• /help - показать эту справку\n\n"
        "*Ограничения:*\n"
        "• Максимальная длина текста: 2000 символов\n"
        "• Лимит: 5 видео в день\n"
        "• Генерация занимает 2-5 минут"
    )

    await update.message.reply_text(help_message, parse_mode='Markdown')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = update.effective_user.id

    status_message = await video_service.get_task_status_message(user_id)
    await update.message.reply_text(status_message)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    user_id = update.effective_user.id

    success, message = await video_service.cancel_task(user_id)

    if success:
        await update.message.reply_text(f"✅ {message}")
        # Clear conversation state
        context.user_data.clear()
    else:
        await update.message.reply_text(f"ℹ️ {message}")

    logger.info(f"User {user_id} attempted to cancel task: {success}")
