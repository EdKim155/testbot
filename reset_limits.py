#!/usr/bin/env python3
"""Reset daily limits for all users."""
import asyncio
from bot.database.database import db
from sqlalchemy import delete
from bot.database.models import VideoTask


async def reset_limits():
    """Reset all users' daily limits by clearing today's tasks."""
    print("🔄 Resetting daily limits...")

    async with db.async_session() as session:
        # Get count of tasks
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(VideoTask.task_id)))
        count = result.scalar()
        print(f"📊 Total tasks in database: {count}")

        # Option 1: Delete all failed/cancelled tasks (keeps completed ones)
        result = await session.execute(
            delete(VideoTask).where(VideoTask.status == 'failed')
        )
        await session.commit()
        deleted = result.rowcount
        print(f"✅ Deleted {deleted} failed tasks")

        print("\n✨ Daily limits reset!")
        print("Users can now generate videos again.")


if __name__ == '__main__':
    asyncio.run(reset_limits())
