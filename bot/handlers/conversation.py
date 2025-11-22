"""Conversation handlers for video generation flow."""
import logging
import os
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TimedOut, NetworkError

from bot.services.video_service import video_service
from bot.utils.validators import (
    validate_avatar_id,
    validate_voice_id,
    validate_text,
    parse_single_message
)
from bot.config import Config

logger = logging.getLogger(__name__)

# Conversation states
AVATAR_ID, VOICE_ID, TEXT_INPUT = range(3)


async def retry_with_backoff(func, max_retries=4, initial_delay=2.0):
    """
    Retry a function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 4)
        initial_delay: Initial delay in seconds (default: 2.0)

    Returns:
        Result of the function call

    Raises:
        The last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func()
        except (TimedOut, NetworkError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(f"All {max_retries} retry attempts failed")
                raise
        except Exception as e:
            # For non-network errors, don't retry
            logger.error(f"Non-retryable error: {e}")
            raise

    # This should never be reached, but just in case
    if last_exception:
        raise last_exception


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start video generation conversation."""
    user_id = update.effective_user.id

    # Check if user can generate video
    can_generate, error_message = await video_service.can_user_generate_video(user_id)

    if not can_generate:
        await update.message.reply_text(f"❌ {error_message}")
        return ConversationHandler.END

    await update.message.reply_text(
        "🎬 *Начнем создание видео!*\n\n"
        "🎭 Отправьте *ID аватара*:\n"
        "Используйте /avatars для просмотра доступных аватаров",
        parse_mode='Markdown'
    )

    return AVATAR_ID


async def receive_avatar_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive avatar ID from user."""
    message_text = update.message.text.strip()

    # Validate avatar ID
    is_valid, error = validate_avatar_id(message_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {error}\n\nПопробуйте снова:")
        return AVATAR_ID

    # Detect if this is a talking_photo_id (32 hex characters) and add prefix
    # Talking photo IDs are typically 32 hexadecimal characters without dashes
    import re
    if re.match(r'^[0-9a-f]{32}$', message_text):
        # This looks like a talking_photo_id, add prefix
        context.user_data['avatar_id'] = f"talking_photo:{message_text}"
        logger.info(f"Detected talking_photo_id, added prefix: talking_photo:{message_text}")
    else:
        # Regular avatar_id
        context.user_data['avatar_id'] = message_text

    await update.message.reply_text(
        "✅ ID аватара принят!\n\n"
        "Теперь отправьте *ID голоса*:\n"
        "Используйте /voices для просмотра доступных голосов",
        parse_mode='Markdown'
    )

    return VOICE_ID


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive photo from user and create talking photo."""
    from bot.services.heygen_api import heygen_api

    # Check if message contains photo
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте фото (не файл)!\n\n"
            "Используйте функцию отправки фото в Telegram."
        )
        return PHOTO

    # Get the highest resolution photo
    photo = update.message.photo[-1]

    status_msg = await update.message.reply_text("⏳ Загружаю фото и создаю аватар...")

    try:
        # Download photo
        file = await context.bot.get_file(photo.file_id)
        photo_path = f"{Config.TEMP_VIDEO_DIR}/photo_{update.effective_user.id}.jpg"

        # Ensure temp directory exists
        os.makedirs(Config.TEMP_VIDEO_DIR, exist_ok=True)

        await file.download_to_drive(photo_path)
        logger.info(f"Photo downloaded: {photo_path}")

        # Upload photo to HeyGen and get HeyGen URL
        await status_msg.edit_text("⏳ Загружаю фото в HeyGen...")
        heygen_image_url = await heygen_api.upload_image(photo_path)

        if not heygen_image_url:
            await status_msg.edit_text(
                "❌ Не удалось загрузить фото. Попробуйте другое фото."
            )
            # Clean up photo file
            try:
                os.remove(photo_path)
            except:
                pass
            return PHOTO

        logger.info(f"Image uploaded to HeyGen: {heygen_image_url}")

        # Create talking photo with HeyGen URL
        await status_msg.edit_text("⏳ Создаю говорящий аватар из вашего фото...")
        talking_photo_id = await heygen_api.create_talking_photo(heygen_image_url)

        # Clean up photo file
        try:
            os.remove(photo_path)
        except:
            pass

        if not talking_photo_id:
            await status_msg.edit_text(
                "❌ Не удалось создать аватар из фото.\n\n"
                "Убедитесь, что на фото четко видно лицо."
            )
            return PHOTO

        # Store talking photo ID
        context.user_data['talking_photo_id'] = talking_photo_id

        await status_msg.edit_text(
            "✅ Аватар создан!\n\n"
            "Теперь отправьте *ID голоса*:\n"
            "Используйте /voices для просмотра доступных голосов",
            parse_mode='Markdown'
        )

        return VOICE_ID

    except Exception as e:
        logger.error(f"Error processing photo: {str(e)}")
        await status_msg.edit_text(
            "❌ Произошла ошибка при обработке фото. Попробуйте снова."
        )
        return PHOTO


async def receive_voice_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive voice ID from user."""
    message_text = update.message.text.strip()

    # Validate voice ID
    is_valid, error = validate_voice_id(message_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {error}\n\nПопробуйте снова:")
        return VOICE_ID

    # Store voice ID
    context.user_data['voice_id'] = message_text

    await update.message.reply_text(
        "✅ ID голоса принят!\n\n"
        "Теперь отправьте *текст для озвучки* (до 2000 символов):",
        parse_mode='Markdown'
    )

    return TEXT_INPUT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive text input from user."""
    message_text = update.message.text.strip()

    # Validate text
    is_valid, error = validate_text(message_text)
    if not is_valid:
        await update.message.reply_text(f"❌ {error}\n\nПопробуйте снова:")
        return TEXT_INPUT

    # Store text
    context.user_data['text'] = message_text

    # Get all parameters
    avatar_id = context.user_data.get('avatar_id')
    voice_id = context.user_data['voice_id']

    # Show confirmation
    await update.message.reply_text(
        "📋 *Параметры вашего видео:*\n\n"
        f"🎭 Аватар: `{avatar_id}`\n"
        f"🎤 Голос: `{voice_id}`\n"
        f"📝 Текст: {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n\n"
        "⏳ Начинаю генерацию...",
        parse_mode='Markdown'
    )

    # Start video generation
    await generate_video(
        update,
        context,
        avatar_id,
        voice_id,
        message_text
    )

    return ConversationHandler.END


async def process_single_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parsed_data: tuple
):
    """Process single-message format."""
    avatar_id, voice_id, text = parsed_data

    # Validate all inputs
    is_valid, error = validate_avatar_id(avatar_id)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Ошибка в ID аватара: {error}\n\n"
            "Используйте формат: `avatar_id | voice_id | текст`",
            parse_mode='Markdown'
        )
        return AVATAR_ID

    is_valid, error = validate_voice_id(voice_id)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Ошибка в ID голоса: {error}\n\n"
            "Используйте формат: `avatar_id | voice_id | текст`",
            parse_mode='Markdown'
        )
        return AVATAR_ID

    is_valid, error = validate_text(text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ Ошибка в тексте: {error}\n\n"
            "Используйте формат: `avatar_id | voice_id | текст`",
            parse_mode='Markdown'
        )
        return AVATAR_ID

    # Detect if this is a talking_photo_id and add prefix
    import re
    if re.match(r'^[0-9a-f]{32}$', avatar_id):
        avatar_id = f"talking_photo:{avatar_id}"
        logger.info(f"Detected talking_photo_id in single message, added prefix")

    # Show confirmation
    await update.message.reply_text(
        "📋 *Параметры вашего видео:*\n\n"
        f"🎭 Аватар: `{avatar_id}`\n"
        f"🎤 Голос: `{voice_id}`\n"
        f"📝 Текст: {text[:100]}{'...' if len(text) > 100 else ''}\n\n"
        "⏳ Начинаю генерацию...",
        parse_mode='Markdown'
    )

    # Start video generation
    await generate_video(update, context, avatar_id, voice_id, text)

    return ConversationHandler.END


async def generate_video_with_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    talking_photo_id: str,
    voice_id: str,
    text: str
):
    """Generate video with talking photo."""
    user = update.effective_user

    try:
        # Create video task with talking photo
        task_id = await video_service.create_video_task_with_photo(
            user.id,
            user.username,
            talking_photo_id,
            voice_id,
            text
        )

        logger.info(f"Starting video generation with photo for task {task_id}")

        # Notify user
        status_message = await update.message.reply_text(
            "⚙️ Генерация начата. Это может занять 2-5 минут...\n\n"
            "Вы можете использовать /status для проверки прогресса."
        )

        # Generate video in background
        success, error_msg = await video_service.generate_video(task_id)

        if success:
            # Download video
            await context.bot.edit_message_text(
                "📥 Видео готово! Скачиваю...",
                chat_id=update.effective_chat.id,
                message_id=status_message.message_id
            )

            video_path = await video_service.download_task_video(task_id)

            if video_path and os.path.exists(video_path):
                # Send video
                await context.bot.edit_message_text(
                    "📤 Отправляю видео...",
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id
                )

                try:
                    # Use retry logic for sending video
                    async def send_video_with_retry():
                        with open(video_path, 'rb') as video_file:
                            return await context.bot.send_video(
                                chat_id=update.effective_chat.id,
                                video=video_file,
                                caption="✅ *Ваше видео готово!*\n\nХотите создать еще одно? Используйте /generate",
                                parse_mode='Markdown'
                            )

                    await retry_with_backoff(send_video_with_retry)

                    # Delete status message
                    await status_message.delete()

                    logger.info(f"Video sent successfully for task {task_id}")

                except Exception as e:
                    logger.error(f"Failed to send video after retries: {e}")
                    await context.bot.edit_message_text(
                        "❌ Не удалось отправить видео из-за проблем с сетью. Попробуйте позже.",
                        chat_id=update.effective_chat.id,
                        message_id=status_message.message_id
                    )

                finally:
                    # Clean up video file
                    try:
                        os.remove(video_path)
                    except Exception as e:
                        logger.error(f"Error deleting video file: {e}")
            else:
                await context.bot.edit_message_text(
                    "❌ Не удалось скачать видео. Попробуйте позже.",
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id
                )
        else:
            await context.bot.edit_message_text(
                f"❌ {error_msg}",
                chat_id=update.effective_chat.id,
                message_id=status_message.message_id
            )

    except Exception as e:
        logger.error(f"Error in generate_video_with_photo: {str(e)}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации видео. Попробуйте позже."
        )

    finally:
        # Clear user data
        context.user_data.clear()


async def generate_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    avatar_id: str,
    voice_id: str,
    text: str
):
    """Generate video with given parameters."""
    user = update.effective_user

    try:
        # Create video task
        task_id = await video_service.create_video_task(
            user.id,
            user.username,
            avatar_id,
            voice_id,
            text
        )

        logger.info(f"Starting video generation for task {task_id}")

        # Notify user
        status_message = await update.message.reply_text(
            "⚙️ Генерация начата. Это может занять 2-5 минут...\n\n"
            "Вы можете использовать /status для проверки прогресса."
        )

        # Generate video in background
        success, error_msg = await video_service.generate_video(task_id)

        if success:
            # Download video
            await context.bot.edit_message_text(
                "📥 Видео готово! Скачиваю...",
                chat_id=update.effective_chat.id,
                message_id=status_message.message_id
            )

            video_path = await video_service.download_task_video(task_id)

            if video_path and os.path.exists(video_path):
                # Send video
                await context.bot.edit_message_text(
                    "📤 Отправляю видео...",
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id
                )

                try:
                    # Use retry logic for sending video
                    async def send_video_with_retry():
                        with open(video_path, 'rb') as video_file:
                            return await context.bot.send_video(
                                chat_id=update.effective_chat.id,
                                video=video_file,
                                caption="✅ *Ваше видео готово!*\n\nХотите создать еще одно? Используйте /generate",
                                parse_mode='Markdown'
                            )

                    await retry_with_backoff(send_video_with_retry)

                    # Delete status message
                    await status_message.delete()

                    logger.info(f"Video sent successfully for task {task_id}")

                except Exception as e:
                    logger.error(f"Failed to send video after retries: {e}")
                    await context.bot.edit_message_text(
                        "❌ Не удалось отправить видео из-за проблем с сетью. Попробуйте позже.",
                        chat_id=update.effective_chat.id,
                        message_id=status_message.message_id
                    )

                finally:
                    # Clean up video file
                    try:
                        os.remove(video_path)
                    except Exception as e:
                        logger.error(f"Error deleting video file: {e}")
            else:
                await context.bot.edit_message_text(
                    "❌ Не удалось скачать видео. Попробуйте позже.",
                    chat_id=update.effective_chat.id,
                    message_id=status_message.message_id
                )
        else:
            await context.bot.edit_message_text(
                f"❌ {error_msg}",
                chat_id=update.effective_chat.id,
                message_id=status_message.message_id
            )

    except Exception as e:
        logger.error(f"Error in generate_video: {str(e)}")
        await update.message.reply_text(
            "❌ Произошла ошибка при генерации видео. Попробуйте позже."
        )

    finally:
        # Clear user data
        context.user_data.clear()


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Генерация отменена. Используйте /generate для создания нового видео."
    )
    return ConversationHandler.END


async def handle_regular_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages outside conversation."""
    message_text = update.message.text.strip()

    # Try to parse as single-message format
    parsed = parse_single_message(message_text)

    if parsed:
        user_id = update.effective_user.id

        # Check if user can generate video
        can_generate, error_message = await video_service.can_user_generate_video(user_id)

        if not can_generate:
            await update.message.reply_text(f"❌ {error_message}")
            return

        # Process the message
        await process_single_message(update, context, parsed)
    else:
        # Unknown message
        await update.message.reply_text(
            "ℹ️ Используйте /help для получения инструкций или /generate для создания видео."
        )
