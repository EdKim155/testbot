"""Database connection and session management."""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func

from bot.database.models import Base, User, VideoTask
from bot.config import Config


class Database:
    """Database manager for async operations."""

    def __init__(self):
        self.engine = create_async_engine(Config.DATABASE_URL, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        return self.async_session()

    async def get_or_create_user(self, user_id: int, username: Optional[str] = None) -> User:
        """Get existing user or create new one."""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                user = User(user_id=user_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)

            return user

    async def create_video_task(
        self, user_id: int, avatar_id: str, voice_id: str, input_text: str
    ) -> VideoTask:
        """Create new video generation task."""
        async with self.async_session() as session:
            task = VideoTask(
                user_id=user_id,
                avatar_id=avatar_id,
                voice_id=voice_id,
                input_text=input_text,
                status='pending'
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def update_task_status(
        self,
        task_id: int,
        status: str,
        heygen_video_id: Optional[str] = None,
        video_url: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[VideoTask]:
        """Update video task status."""
        async with self.async_session() as session:
            result = await session.execute(select(VideoTask).where(VideoTask.task_id == task_id))
            task = result.scalar_one_or_none()

            if task:
                task.status = status
                if heygen_video_id:
                    task.heygen_video_id = heygen_video_id
                if video_url:
                    task.video_url = video_url
                if error_message:
                    task.error_message = error_message
                if status == 'completed':
                    task.completed_at = datetime.utcnow()

                await session.commit()
                await session.refresh(task)

            return task

    async def get_task_by_id(self, task_id: int) -> Optional[VideoTask]:
        """Get task by ID."""
        async with self.async_session() as session:
            result = await session.execute(select(VideoTask).where(VideoTask.task_id == task_id))
            return result.scalar_one_or_none()

    async def get_user_active_task(self, user_id: int) -> Optional[VideoTask]:
        """Get user's active (pending or processing) task."""
        async with self.async_session() as session:
            result = await session.execute(
                select(VideoTask)
                .where(VideoTask.user_id == user_id)
                .where(VideoTask.status.in_(['pending', 'processing']))
                .order_by(VideoTask.created_at.desc())
            )
            return result.scalar_one_or_none()

    async def get_user_daily_requests(self, user_id: int) -> int:
        """Get number of user's requests today."""
        async with self.async_session() as session:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            result = await session.execute(
                select(func.count(VideoTask.task_id))
                .where(VideoTask.user_id == user_id)
                .where(VideoTask.created_at >= today_start)
            )
            return result.scalar() or 0

    async def increment_user_videos(self, user_id: int):
        """Increment user's total generated videos count."""
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if user:
                user.total_videos_generated += 1
                user.last_request_date = datetime.utcnow()
                await session.commit()

    async def get_user_history(self, user_id: int, limit: int = 10) -> List[VideoTask]:
        """Get user's video generation history."""
        async with self.async_session() as session:
            result = await session.execute(
                select(VideoTask)
                .where(VideoTask.user_id == user_id)
                .order_by(VideoTask.created_at.desc())
                .limit(limit)
            )
            return result.scalars().all()


# Global database instance
db = Database()
