"""
Cloud Storage Service - Cloudinary (Nigeria Friendly)
Created by: chAs
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Optional

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for managing cloud storage using Cloudinary."""
    
    def __init__(self):
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
    
    async def upload_file(
        self,
        file_data: bytes,
        filename: Optional[str] = None,
        content_type: str = "application/octet-stream",
        folder: str = "videos",
    ) -> str:
        """Upload file to Cloudinary."""
        
        import io
        import uuid
        
        if not filename:
            filename = f"{folder}/{uuid.uuid4()}"
        else:
            filename = f"{folder}/{filename}"
        
        try:
            # Determine resource type based on content
            resource_type = "auto"
            if "video" in content_type:
                resource_type = "video"
            elif "image" in content_type:
                resource_type = "image"
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                io.BytesIO(file_data),
                public_id=filename,
                resource_type=resource_type,
                overwrite=True,
            )
            
            url = result.get("secure_url")
            logger.info(f"File uploaded to Cloudinary: {filename}")
            return url
            
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")
            raise
    
    async def upload_image(
        self,
        image_data: bytes,
        filename: Optional[str] = None,
        folder: str = "images",
        transformation: Optional[dict] = None,
    ) -> str:
        """Upload image with optional transformation."""
        
        import io
        import uuid
        
        if not filename:
            filename = f"{folder}/{uuid.uuid4()}"
        else:
            filename = f"{folder}/{filename}"
        
        try:
            upload_params = {
                "public_id": filename,
                "resource_type": "image",
                "overwrite": True,
            }
            
            if transformation:
                upload_params["transformation"] = transformation
            
            result = cloudinary.uploader.upload(
                io.BytesIO(image_data),
                **upload_params,
            )
            
            url = result.get("secure_url")
            logger.info(f"Image uploaded to Cloudinary: {filename}")
            return url
            
        except Exception as e:
            logger.error(f"Cloudinary image upload failed: {e}")
            raise
    
    async def upload_video(
        self,
        video_data: bytes,
        filename: Optional[str] = None,
        folder: str = "videos",
    ) -> str:
        """Upload video to Cloudinary."""
        
        import io
        import uuid
        
        if not filename:
            filename = f"{folder}/{uuid.uuid4()}"
        else:
            filename = f"{folder}/{filename}"
        
        try:
            result = cloudinary.uploader.upload(
                io.BytesIO(video_data),
                public_id=filename,
                resource_type="video",
                overwrite=True,
            )
            
            url = result.get("secure_url")
            logger.info(f"Video uploaded to Cloudinary: {filename}")
            return url
            
        except Exception as e:
            logger.error(f"Cloudinary video upload failed: {e}")
            raise
    
    async def delete_file(self, public_id: str) -> bool:
        """Delete file from Cloudinary."""
        
        try:
            result = cloudinary.uploader.destroy(public_id)
            logger.info(f"File deleted from Cloudinary: {public_id}")
            return result.get("result") == "ok"
            
        except Exception as e:
            logger.error(f"Cloudinary delete failed: {e}")
            return False
    
    def get_transformed_url(
        self,
        public_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        crop: Optional[str] = None,
    ) -> str:
        """Get transformed image URL."""
        
        transformation = {}
        
        if width:
            transformation["width"] = width
        if height:
            transformation["height"] = height
        if crop:
            transformation["crop"] = crop
        
        return cloudinary.CloudinaryImage(public_id).build_url(**transformation)
    
    async def download_file(self, url: str) -> bytes:
        """Download file from URL."""
        
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
            return response.content
