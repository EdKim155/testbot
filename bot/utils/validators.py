"""Input validation utilities."""
import re
from typing import Optional, Tuple
from bot.config import Config


def validate_avatar_id(avatar_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate avatar ID format.

    Args:
        avatar_id: Avatar ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not avatar_id or not avatar_id.strip():
        return False, "ID аватара не может быть пустым"

    # Basic validation - HeyGen IDs are typically alphanumeric with underscores/hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', avatar_id):
        return False, "ID аватара содержит недопустимые символы. Используйте только буквы, цифры, дефисы и подчеркивания."

    if len(avatar_id) > 100:
        return False, "ID аватара слишком длинный"

    return True, None


def validate_voice_id(voice_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate voice ID format.

    Args:
        voice_id: Voice ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not voice_id or not voice_id.strip():
        return False, "ID голоса не может быть пустым"

    # Basic validation - HeyGen IDs are typically alphanumeric with underscores/hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', voice_id):
        return False, "ID голоса содержит недопустимые символы. Используйте только буквы, цифры, дефисы и подчеркивания."

    if len(voice_id) > 100:
        return False, "ID голоса слишком длинный"

    return True, None


def validate_text(text: str) -> Tuple[bool, Optional[str]]:
    """
    Validate input text.

    Args:
        text: Text to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text or not text.strip():
        return False, "Текст не может быть пустым"

    if len(text) > Config.MAX_TEXT_LENGTH:
        return False, f"Текст слишком длинный. Максимум {Config.MAX_TEXT_LENGTH} символов. У вас: {len(text)}"

    return True, None


def parse_single_message(message: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse single-message format: avatar_id | voice_id | text

    Args:
        message: Message to parse

    Returns:
        Tuple of (avatar_id, voice_id, text) if valid, None otherwise
    """
    parts = message.split('|')

    if len(parts) != 3:
        return None

    avatar_id = parts[0].strip()
    voice_id = parts[1].strip()
    text = parts[2].strip()

    if not avatar_id or not voice_id or not text:
        return None

    return avatar_id, voice_id, text
