"""Command handlers for the Telegram bot."""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.database.database import db
from bot.services.video_service import video_service
from bot.services.heygen_api import heygen_api

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
        "• /avatars - список доступных аватаров\n"
        "• /voices - список доступных голосов\n"
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
    await update.message.reply_text(status_message, parse_mode='Markdown')


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


async def avatars_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /avatars command - list available avatars."""
    await update.message.reply_text("🔄 Получаю список ваших аватаров...")

    # Get avatars and talking photos
    result = await heygen_api.get_avatars()

    if not result:
        await update.message.reply_text(
            "❌ Не удалось получить список аватаров. Проверьте API ключ."
        )
        return

    avatars = result.get('avatars', [])
    talking_photos = result.get('talking_photos', [])

    # Filter to show only custom/private avatars and talking photos
    custom_avatars = [a for a in avatars if not a.get('is_public', False)]
    public_avatars = [a for a in avatars if a.get('is_public', False)]

    if not custom_avatars and not talking_photos:
        await update.message.reply_text(
            "ℹ️ У вас нет своих кастомных аватаров.\n\n"
            "📸 *Как создать свой аватар:*\n"
            "1. Зайдите на heygen.com\n"
            "2. Создайте Instant Avatar из фото\n"
            "3. Или отправьте фото боту через /generate\n\n"
            f"💡 Доступно публичных аватаров: {len(public_avatars)}\n"
            "Используйте их ID для генерации видео.",
            parse_mode='Markdown'
        )
        return

    # Build message with custom avatars and talking photos first
    message_parts = []

    # Show talking photos (YOUR photos!)
    if talking_photos:
        message_parts.append(f"📸 *ВАШИ ФОТО-АВАТАРЫ ({len(talking_photos)}):*\n")
        for photo in talking_photos[:20]:
            photo_id = photo.get('talking_photo_id', 'N/A')
            photo_name = photo.get('talking_photo_name', 'Unnamed')
            message_parts.append(
                f"\n• *{photo_name}*\n"
                f"  ID: `{photo_id}`"
            )

    # Show custom avatars
    if custom_avatars:
        message_parts.append(f"\n\n🔒 *КАСТОМНЫЕ АВАТАРЫ ({len(custom_avatars)}):*\n")
        for avatar in custom_avatars[:20]:
            avatar_id = avatar.get('avatar_id', 'N/A')
            avatar_name = avatar.get('avatar_name', 'Unnamed')
            message_parts.append(
                f"\n• *{avatar_name}*\n"
                f"  ID: `{avatar_id}`"
            )

    # Add info about public avatars
    message_parts.append(f"\n\n_Также доступно {len(public_avatars)} публичных аватаров_")

    await update.message.reply_text(
        "\n".join(message_parts),
        parse_mode='Markdown'
    )

    logger.info(
        f"User {update.effective_user.id} requested avatars: "
        f"{len(talking_photos)} talking photos, "
        f"{len(custom_avatars)} custom avatars, "
        f"{len(public_avatars)} public avatars"
    )


async def voices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /voices command - list available voices."""
    # Check for language filter
    args = context.args
    language_filter = args[0].lower() if args else None

    await update.message.reply_text("🔄 Получаю список доступных голосов...")

    voices = await heygen_api.get_voices()

    if not voices:
        await update.message.reply_text(
            "❌ Не удалось получить список голосов. Проверьте API ключ."
        )
        return

    # Filter by language if specified
    if language_filter:
        voices = [v for v in voices if language_filter in v.get('language', '').lower()]

    if not voices:
        await update.message.reply_text("ℹ️ Нет доступных голосов.")
        return

    # Show first 20 voices only
    display_voices = voices[:20]

    message_parts = [f"🎤 *Доступные голоса ({len(display_voices)} из {len(voices)}):*\n"]

    if language_filter:
        message_parts[0] = f"🎤 *Голоса ({language_filter}):*\n"

    for voice in display_voices:
        voice_id = voice.get('voice_id', 'N/A')
        voice_name = voice.get('name', 'Unnamed')
        language = voice.get('language', 'N/A')

        message_parts.append(
            f"\n• *{voice_name}*\n"
            f"  ID: `{voice_id}`\n"
            f"  Lang: {language}"
        )

    if len(voices) > 20:
        message_parts.append(
            f"\n\n_...и еще {len(voices) - 20} голосов_\n"
            f"Используйте /voices <язык> для фильтрации\n"
            f"Например: /voices russian или /voices english"
        )

    await update.message.reply_text(
        "\n".join(message_parts),
        parse_mode='Markdown'
    )

    logger.info(f"User {update.effective_user.id} requested voices list")
