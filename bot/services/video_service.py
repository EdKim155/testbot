"""Video generation service combining database and API operations."""
import logging
import os
from typing import Optional
import asyncio

from bot.database.database import db
from bot.services.heygen_api import heygen_api
from bot.config import Config

logger = logging.getLogger(__name__)


class VideoService:
    """Service for managing video generation workflow."""

    async def can_user_generate_video(self, user_id: int) -> tuple[bool, str]:
        """
        Check if user can generate a new video.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (can_generate, error_message)
        """
        # Check if user has reached concurrent tasks limit
        active_tasks_count = await db.get_user_active_tasks_count(user_id)
        if active_tasks_count >= Config.MAX_CONCURRENT_TASKS:
            return False, f"У вас уже {active_tasks_count} активных задач (максимум {Config.MAX_CONCURRENT_TASKS}). Дождитесь завершения или используйте /cancel."

        # Check daily limit
        daily_requests = await db.get_user_daily_requests(user_id)
        if daily_requests >= Config.MAX_DAILY_REQUESTS:
            return False, f"Вы достигли дневного лимита генераций ({Config.MAX_DAILY_REQUESTS}). Попробуйте завтра."

        return True, ""

    async def create_video_task(
        self,
        user_id: int,
        username: Optional[str],
        avatar_id: str,
        voice_id: str,
        input_text: str
    ) -> int:
        """
        Create new video generation task.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            avatar_id: HeyGen avatar ID
            voice_id: HeyGen voice ID
            input_text: Text for video

        Returns:
            Task ID
        """
        # Ensure user exists
        await db.get_or_create_user(user_id, username)

        # Create task
        task = await db.create_video_task(user_id, avatar_id, voice_id, input_text)
        logger.info(f"Created video task {task.task_id} for user {user_id}")

        return task.task_id

    async def create_video_task_with_photo(
        self,
        user_id: int,
        username: Optional[str],
        talking_photo_id: str,
        voice_id: str,
        input_text: str
    ) -> int:
        """
        Create new video generation task with talking photo.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            talking_photo_id: HeyGen talking photo ID
            voice_id: HeyGen voice ID
            input_text: Text for video

        Returns:
            Task ID
        """
        # Ensure user exists
        await db.get_or_create_user(user_id, username)

        # Create task (store talking_photo_id in avatar_id field with prefix)
        # We'll use a prefix to distinguish talking photos from regular avatars
        task = await db.create_video_task(
            user_id,
            f"talking_photo:{talking_photo_id}",  # Prefix to identify talking photos
            voice_id,
            input_text
        )
        logger.info(f"Created video task with talking photo {task.task_id} for user {user_id}")

        return task.task_id

    async def generate_video(self, task_id: int) -> tuple[bool, Optional[str]]:
        """
        Generate video for a task.

        Args:
            task_id: Video task ID

        Returns:
            Tuple of (success, error_message)
        """
        task = await db.get_task_by_id(task_id)
        if not task:
            return False, "Задача не найдена"

        try:
            # Check if this is a talking photo or regular avatar
            if task.avatar_id.startswith("talking_photo:"):
                # Extract talking_photo_id
                talking_photo_id = task.avatar_id.replace("talking_photo:", "")
                # Initiate video generation with talking photo
                video_id = await heygen_api.generate_video(
                    voice_id=task.voice_id,
                    input_text=task.input_text,
                    talking_photo_id=talking_photo_id
                )
            else:
                # Initiate video generation with regular avatar
                video_id = await heygen_api.generate_video(
                    voice_id=task.voice_id,
                    input_text=task.input_text,
                    avatar_id=task.avatar_id
                )

            if not video_id:
                await db.update_task_status(
                    task_id,
                    'failed',
                    error_message='Не удалось инициировать генерацию видео'
                )
                return False, "Не удалось создать видео. Проверьте правильность ID аватара и голоса."

            # Update task with HeyGen video ID
            await db.update_task_status(task_id, 'processing', heygen_video_id=video_id)

            # Wait for video completion
            video_url = await heygen_api.wait_for_video(video_id)

            if not video_url:
                await db.update_task_status(
                    task_id,
                    'failed',
                    error_message='Генерация видео превысила лимит времени или завершилась с ошибкой'
                )
                return False, "Генерация видео заняла слишком много времени или завершилась с ошибкой. Попробуйте снова."

            # Update task with video URL
            await db.update_task_status(task_id, 'completed', video_url=video_url)

            # Increment user's video count
            await db.increment_user_videos(task.user_id)

            logger.info(f"Video generation completed for task {task_id}")
            return True, None

        except Exception as e:
            logger.error(f"Error generating video for task {task_id}: {str(e)}")
            await db.update_task_status(
                task_id,
                'failed',
                error_message=str(e)
            )
            return False, "Произошла ошибка при генерации видео. Попробуйте позже."

    async def download_task_video(self, task_id: int) -> Optional[str]:
        """
        Download video for a completed task.

        Args:
            task_id: Video task ID

        Returns:
            Local file path if successful, None otherwise
        """
        task = await db.get_task_by_id(task_id)
        if not task or task.status != 'completed' or not task.video_url:
            return None

        # Generate local file path
        file_path = os.path.join(
            Config.TEMP_VIDEO_DIR,
            f"video_{task_id}_{task.heygen_video_id}.mp4"
        )

        # Download video
        success = await heygen_api.download_video(task.video_url, file_path)

        if success:
            return file_path
        else:
            return None

    async def cancel_task(self, user_id: int, task_id: Optional[int] = None) -> tuple[bool, str]:
        """
        Cancel user's active task(s).

        Args:
            user_id: Telegram user ID
            task_id: Optional specific task ID to cancel. If None, cancels all active tasks.

        Returns:
            Tuple of (success, message)
        """
        if task_id:
            # Cancel specific task
            task = await db.get_task_by_id(task_id)
            if not task or task.user_id != user_id:
                return False, "Задача не найдена."

            if task.status not in ['pending', 'processing']:
                return False, "Эта задача уже завершена или отменена."

            await db.update_task_status(
                task_id,
                'failed',
                error_message='Отменено пользователем'
            )
            logger.info(f"Task {task_id} cancelled by user {user_id}")
            return True, f"Задача #{task_id} отменена."

        else:
            # Cancel all active tasks
            active_tasks = await db.get_user_active_tasks(user_id)

            if not active_tasks:
                return False, "У вас нет активных задач для отмены."

            for task in active_tasks:
                await db.update_task_status(
                    task.task_id,
                    'failed',
                    error_message='Отменено пользователем'
                )

            logger.info(f"{len(active_tasks)} tasks cancelled by user {user_id}")
            return True, f"Отменено задач: {len(active_tasks)}."

    async def get_task_status_message(self, user_id: int) -> str:
        """
        Get status message for user's active tasks.

        Args:
            user_id: Telegram user ID

        Returns:
            Status message
        """
        active_tasks = await db.get_user_active_tasks(user_id)

        if not active_tasks:
            return "У вас нет активных задач генерации видео."

        message_parts = [f"📊 *Активные задачи ({len(active_tasks)}):*\n"]

        for i, task in enumerate(active_tasks, 1):
            status_emoji = "⏳" if task.status == 'pending' else "⚙️"
            status_text = "в очереди" if task.status == 'pending' else "генерируется"

            # Truncate text for display
            text_preview = task.input_text[:50] + "..." if len(task.input_text) > 50 else task.input_text

            message_parts.append(
                f"{i}. {status_emoji} Задача #{task.task_id} - {status_text}\n"
                f"   Текст: {text_preview}\n"
            )

        return "\n".join(message_parts)


# Global video service instance
video_service = VideoService()
