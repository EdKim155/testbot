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
        avatar_id: str,
        voice_id: str,
        input_text: str
    ) -> Optional[str]:
        """
        Initiate video generation.

        Args:
            avatar_id: HeyGen avatar ID
            voice_id: HeyGen voice ID
            input_text: Text to be spoken by avatar

        Returns:
            video_id if successful, None otherwise
        """
        url = f"{self.base_url}/v2/video/generate"

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": "normal"
                    },
                    "voice": {
                        "type": "text",
                        "voice_id": voice_id,
                        "input_text": input_text
                    }
                }
            ],
            "dimension": {
                "width": Config.VIDEO_WIDTH,
                "height": Config.VIDEO_HEIGHT
            }
        }

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
        url = f"{self.base_url}/v2/video/{video_id}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
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


# Global HeyGen API instance
heygen_api = HeyGenAPI()
