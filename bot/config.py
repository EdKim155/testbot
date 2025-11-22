"""Configuration management for the Telegram bot."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration from environment variables."""

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # HeyGen API Configuration
    HEYGEN_API_KEY = os.getenv('HEYGEN_API_KEY')
    HEYGEN_API_BASE_URL = 'https://api.heygen.com'

    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///bot.db')

    # Rate Limiting
    MAX_DAILY_REQUESTS = int(os.getenv('MAX_DAILY_REQUESTS', '5'))
    MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', '3'))

    # Video Generation Settings
    VIDEO_CHECK_INTERVAL = int(os.getenv('VIDEO_CHECK_INTERVAL', '15'))  # seconds
    VIDEO_GENERATION_TIMEOUT = int(os.getenv('VIDEO_GENERATION_TIMEOUT', '600'))  # 10 minutes
    MAX_TEXT_LENGTH = int(os.getenv('MAX_TEXT_LENGTH', '2000'))

    # Video Settings
    VIDEO_WIDTH = int(os.getenv('VIDEO_WIDTH', '1920'))
    VIDEO_HEIGHT = int(os.getenv('VIDEO_HEIGHT', '1080'))

    # Temporary Files
    TEMP_VIDEO_DIR = os.getenv('TEMP_VIDEO_DIR', './temp_videos')

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not cls.HEYGEN_API_KEY:
            raise ValueError("HEYGEN_API_KEY is required")

        # Create temp directory if it doesn't exist
        os.makedirs(cls.TEMP_VIDEO_DIR, exist_ok=True)


# Validate configuration on import
Config.validate()
