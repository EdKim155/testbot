"""HeyGen API integration service."""
import asyncio
import logging
from typing import Optional, Dict, Any
import aiohttp

from bot.config import Config

logger = logging.getLogger(__name__)


class HeyGenAPI:
    """Service for interacting with HeyGen API."""

    def __init__(self):
        self.api_key = Config.HEYGEN_API_KEY
        self.base_url = Config.HEYGEN_API_BASE_URL
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    async def generate_video(
        self,
        voice_id: str,
        input_text: str,
        avatar_id: str = None,
        talking_photo_id: str = None
    ) -> Optional[str]:
        """
        Initiate video generation.

        Args:
            voice_id: HeyGen voice ID
            input_text: Text to be spoken by avatar
            avatar_id: HeyGen avatar ID (optional)
            talking_photo_id: Talking photo ID (optional)

        Returns:
            video_id if successful, None otherwise
        """
        url = f"{self.base_url}/v2/video/generate"

        # Build character config based on what's provided
        if talking_photo_id:
            character = {
                "type": "talking_photo",
                "talking_photo_id": talking_photo_id,
                "talking_photo_style": "normal"  # Options: normal, circle, square
            }
        elif avatar_id:
            character = {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal"
            }
        else:
            logger.error("Either avatar_id or talking_photo_id must be provided")
            return None

        payload = {
            "video_inputs": [
                {
                    "character": character,
                    "voice": {
                        "type": "text",
                        "input_text": input_text,
                        "voice_id": voice_id
                    },
                    "background": {
                        "type": "color",
                        "value": "#FFFFFF"
                    }
                }
            ],
            "dimension": {
                "width": Config.VIDEO_WIDTH,
                "height": Config.VIDEO_HEIGHT
            },
            "test": False,
            "caption": False
        }

        # Log payload for debugging (without sensitive data)
        logger.info(f"Generating video with payload: character_type={character.get('type')}, voice_id={voice_id}, text_length={len(input_text)}")
        logger.debug(f"Full payload: {payload}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        video_id = data.get('data', {}).get('video_id')
                        logger.info(f"Video generation initiated: {video_id}")
                        return video_id
                    else:
                        error_text = await response.text()
                        logger.error(f"HeyGen API error: {response.status} - {error_text}")
                        logger.error(f"Failed payload: {payload}")
                        return None

        except asyncio.TimeoutError:
            logger.error("HeyGen API request timeout")
            return None
        except Exception as e:
            logger.error(f"Error calling HeyGen API: {str(e)}")
            return None

    async def get_video_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Check video generation status.

        Args:
            video_id: HeyGen video ID

        Returns:
            Dictionary with status information or None
        """
        # Use v1 endpoint as v2 video status endpoint has issues (404)
        url = f"{self.base_url}/v1/video_status.get"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params={'video_id': video_id},
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        video_data = data.get('data', {})

                        return {
                            'status': video_data.get('status'),
                            'video_url': video_data.get('video_url'),
                            'error': video_data.get('error')
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Error checking video status: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error checking video status: {str(e)}")
            return None

    async def wait_for_video(
        self,
        video_id: str,
        timeout: int = Config.VIDEO_GENERATION_TIMEOUT
    ) -> Optional[str]:
        """
        Wait for video generation to complete.

        Args:
            video_id: HeyGen video ID
            timeout: Maximum time to wait in seconds

        Returns:
            Video URL if successful, None otherwise
        """
        start_time = asyncio.get_event_loop().time()
        check_interval = Config.VIDEO_CHECK_INTERVAL

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                logger.error(f"Video generation timeout for {video_id}")
                return None

            status_data = await self.get_video_status(video_id)

            if not status_data:
                logger.error("Failed to get video status")
                await asyncio.sleep(check_interval)
                continue

            status = status_data.get('status')

            if status == 'completed':
                video_url = status_data.get('video_url')
                logger.info(f"Video generation completed: {video_url}")
                return video_url

            elif status == 'failed':
                error = status_data.get('error', 'Unknown error')
                logger.error(f"Video generation failed: {error}")
                return None

            elif status in ['pending', 'processing']:
                logger.info(f"Video {video_id} status: {status}")
                await asyncio.sleep(check_interval)

            else:
                logger.warning(f"Unknown video status: {status}")
                await asyncio.sleep(check_interval)

    async def download_video(self, video_url: str, file_path: str) -> bool:
        """
        Download video from URL.

        Args:
            video_url: URL of the video
            file_path: Local path to save video

        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    video_url,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status == 200:
                        with open(file_path, 'wb') as f:
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        logger.info(f"Video downloaded: {file_path}")
                        return True
                    else:
                        logger.error(f"Failed to download video: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            return False

    async def get_avatars(self) -> Optional[Dict[str, list]]:
        """
        Get list of available avatars and talking photos.

        Returns:
            Dictionary with 'avatars' and 'talking_photos' lists, or None
        """
        url = f"{self.base_url}/v2/avatars"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result_data = data.get('data', {})
                        avatars = result_data.get('avatars', [])
                        talking_photos = result_data.get('talking_photos', [])
                        logger.info(f"Retrieved {len(avatars)} avatars and {len(talking_photos)} talking photos")
                        return {
                            'avatars': avatars,
                            'talking_photos': talking_photos
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Error getting avatars: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error getting avatars: {str(e)}")
            return None

    async def create_talking_photo(self, photo_url: str) -> Optional[str]:
        """
        Create a talking photo avatar from an image URL.

        Args:
            photo_url: URL of the photo to use

        Returns:
            talking_photo_id if successful, None otherwise
        """
        url = f"{self.base_url}/v1/talking_photo"

        payload = {
            "image_url": photo_url
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        talking_photo_id = data.get('data', {}).get('talking_photo_id')
                        logger.info(f"Created talking photo: {talking_photo_id}")
                        return talking_photo_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Error creating talking photo: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error creating talking photo: {str(e)}")
            return None

    async def upload_image(self, file_path: str) -> Optional[str]:
        """
        Upload an image to HeyGen and get URL.

        Args:
            file_path: Local path to the image file

        Returns:
            Image URL if successful, None otherwise
        """
        url = "https://upload.heygen.com/v1/asset"

        try:
            # Read file into memory
            with open(file_path, 'rb') as f:
                file_data = f.read()

            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                # Try 'file' field name (standard for file uploads)
                form.add_field(
                    'file',
                    file_data,
                    filename='photo.jpg',
                    content_type='image/jpeg'
                )

                headers = {'X-Api-Key': self.api_key}

                async with session.post(
                    url,
                    data=form,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                        if response.status == 200:
                            data = await response.json()
                            image_url = data.get('data', {}).get('url')
                            logger.info(f"Image uploaded: {image_url}")
                            return image_url
                        else:
                            error_text = await response.text()
                            logger.error(f"Error uploading image: {response.status} - {error_text}")
                            return None

        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            return None

    async def get_voices(self) -> Optional[list]:
        """
        Get list of available voices.

        Returns:
            List of voices or None
        """
        url = f"{self.base_url}/v2/voices"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        voices = data.get('data', {}).get('voices', [])
                        logger.info(f"Retrieved {len(voices)} voices")
                        return voices
                    else:
                        error_text = await response.text()
                        logger.error(f"Error getting voices: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error getting voices: {str(e)}")
            return None

    async def get_avatar_groups(self) -> Optional[list]:
        """
        Get list of available avatar groups (for photo avatars/instant avatars).

        Returns:
            List of avatar groups or None
        """
        url = f"{self.base_url}/v2/avatar_groups"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        groups = data.get('data', {}).get('avatar_groups', [])
                        logger.info(f"Retrieved {len(groups)} avatar groups")
                        return groups
                    else:
                        error_text = await response.text()
                        logger.error(f"Error getting avatar groups: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error getting avatar groups: {str(e)}")
            return None

    async def get_avatars_in_group(self, group_id: str) -> Optional[list]:
        """
        Get list of avatars in a specific avatar group.

        Args:
            group_id: Avatar group ID

        Returns:
            List of avatars in the group or None
        """
        url = f"{self.base_url}/v2/avatar_groups/{group_id}/avatars"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        avatars = data.get('data', {}).get('avatars', [])
                        logger.info(f"Retrieved {len(avatars)} avatars in group {group_id}")
                        return avatars
                    else:
                        error_text = await response.text()
                        logger.error(f"Error getting avatars in group: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error getting avatars in group: {str(e)}")
            return None


# Global HeyGen API instance
heygen_api = HeyGenAPI()
