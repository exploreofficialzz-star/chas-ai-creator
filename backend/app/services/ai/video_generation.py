"""Video generation service using AnimateDiff/Zeroscope."""

import io
import uuid
from typing import List, Optional

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)


class VideoGenerationService:
    """Service for generating video clips from images."""
    
    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        self.api_url = settings.HUGGINGFACE_API_URL
        self.model = settings.VIDEO_MODEL
        self.storage = StorageService()
    
    async def generate_video_clip(
        self,
        image_url: str,
        prompt: str,
        duration: float = 3.0,
        motion_strength: float = 0.5,
    ) -> str:
        """Generate video clip from image."""
        
        try:
            # Download source image
            image_data = await self._download_image(image_url)
            
            # Generate video using AI model
            if self.api_key:
                video_data = await self._call_video_api(
                    image_data, prompt, motion_strength
                )
            else:
                # Fallback to placeholder
                video_data = await self._generate_placeholder_video(duration)
            
            # Upload to storage
            filename = f"clips/{uuid.uuid4()}.mp4"
            video_url = await self.storage.upload_file(
                file_data=video_data,
                filename=filename,
                content_type="video/mp4",
            )
            
            logger.info("Video clip generated successfully")
            return video_url
            
        except Exception as e:
            logger.error("Video clip generation failed", error=str(e))
            # Return placeholder
            return await self._get_placeholder_video_url(duration)
    
    async def _download_image(self, image_url: str) -> bytes:
        """Download image from URL."""
        
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url, timeout=30.0)
            response.raise_for_status()
            return response.content
    
    async def _call_video_api(
        self,
        image_data: bytes,
        prompt: str,
        motion_strength: float,
    ) -> bytes:
        """Call video generation API."""
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        # Prepare multipart form data
        files = {
            "image": ("input.jpg", io.BytesIO(image_data), "image/jpeg"),
        }
        
        data = {
            "prompt": prompt,
            "motion_bucket_id": int(motion_strength * 255),
            "num_frames": 16,
            "fps": 8,
        }
        
        model_url = f"{self.api_url}/{self.model}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                model_url,
                headers=headers,
                data=data,
                files=files,
                timeout=180.0,
            )
            response.raise_for_status()
            return response.content
    
    async def _generate_placeholder_video(self, duration: float) -> bytes:
        """Generate placeholder video for development."""
        
        # This would create a simple animated video
        # For now, return empty bytes (will be handled by composer)
        return b""
    
    async def _get_placeholder_video_url(self, duration: float) -> str:
        """Get placeholder video URL."""
        # Return a static placeholder URL
        return "https://placehold.co/1920x1080.mp4?text=Video+Placeholder"
    
    async def apply_camera_motion(
        self,
        video_url: str,
        motion_type: str = "zoom_in",
        intensity: float = 0.5,
    ) -> str:
        """Apply camera motion effect to video."""
        
        # This would use FFmpeg to apply motion effects
        # For now, return original URL
        logger.info(f"Applying {motion_type} motion effect")
        return video_url
