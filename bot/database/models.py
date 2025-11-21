"""Database models for the Telegram bot."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model for storing Telegram user information."""

    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)  # Telegram user ID
    username = Column(String(255), nullable=True)
    registration_date = Column(DateTime, default=datetime.utcnow)
    total_videos_generated = Column(Integer, default=0)
    last_request_date = Column(DateTime, nullable=True)

    # Relationship
    video_tasks = relationship('VideoTask', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username})>"


class VideoTask(Base):
    """Video task model for tracking video generation requests."""

    __tablename__ = 'video_tasks'

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    heygen_video_id = Column(String(255), nullable=True)
    avatar_id = Column(String(255), nullable=False)
    voice_id = Column(String(255), nullable=False)
    input_text = Column(Text, nullable=False)
    status = Column(String(50), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    video_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationship
    user = relationship('User', back_populates='video_tasks')

    def __repr__(self):
        return f"<VideoTask(task_id={self.task_id}, status={self.status})>"
