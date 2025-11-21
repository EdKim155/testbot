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
        # Check if user has active task
        active_task = await db.get_user_active_task(user_id)
        if active_task:
            return False, "У вас уже есть активная задача генерации видео. Используйте /status для проверки статуса или /cancel для отмены."

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

    async def cancel_task(self, user_id: int) -> tuple[bool, str]:
        """
        Cancel user's active task.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (success, message)
        """
        active_task = await db.get_user_active_task(user_id)

        if not active_task:
            return False, "У вас нет активной задачи для отмены."

        await db.update_task_status(
            active_task.task_id,
            'failed',
            error_message='Отменено пользователем'
        )

        logger.info(f"Task {active_task.task_id} cancelled by user {user_id}")
        return True, "Задача генерации видео отменена."

    async def get_task_status_message(self, user_id: int) -> str:
        """
        Get status message for user's active task.

        Args:
            user_id: Telegram user ID

        Returns:
            Status message
        """
        active_task = await db.get_user_active_task(user_id)

        if not active_task:
            return "У вас нет активных задач генерации видео."

        if active_task.status == 'pending':
            return "⏳ Ваша задача находится в очереди..."

        elif active_task.status == 'processing':
            return "⚙️ Ваше видео генерируется. Это может занять 2-5 минут..."

        else:
            return "У вас нет активных задач генерации видео."


# Global video service instance
video_service = VideoService()
