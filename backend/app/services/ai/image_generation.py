"""Image generation service using Stable Diffusion."""

import base64
import io
import uuid
from typing import Optional

import httpx
from PIL import Image

from app.config import settings
from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)


class ImageGenerationService:
    """Service for generating images using AI models."""
    
    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        self.api_url = settings.HUGGINGFACE_API_URL
        self.model = settings.IMAGE_MODEL
        self.storage = StorageService()
    
    async def generate_image(
        self,
        prompt: str,
        style: str = "cinematic",
        aspect_ratio: str = "9:16",
        negative_prompt: Optional[str] = None,
        character_consistency: Optional[str] = None,
    ) -> str:
        """Generate image from prompt."""
        
        # Enhance prompt with style
        enhanced_prompt = self._enhance_prompt(prompt, style, character_consistency)
        
        # Set negative prompt
        if not negative_prompt:
            negative_prompt = (
                "blurry, low quality, distorted, deformed, "
                "ugly, duplicate, watermark, signature, text"
            )
        
        try:
            # Use Hugging Face API
            if self.api_key:
                image_data = await self._call_huggingface_api(
                    enhanced_prompt, negative_prompt
                )
            else:
                # Fallback to placeholder
                image_data = self._generate_placeholder_image(aspect_ratio)
            
            # Process and upload image
            image_url = await self._process_and_upload(
                image_data, aspect_ratio
            )
            
            logger.info("Image generated successfully")
            return image_url
            
        except Exception as e:
            logger.error("Image generation failed", error=str(e))
            # Return placeholder
            return await self._get_placeholder_url(aspect_ratio)
    
    def _enhance_prompt(
        self,
        prompt: str,
        style: str,
        character_consistency: Optional[str] = None,
    ) -> str:
        """Enhance prompt with style modifiers."""
        
        style_modifiers = {
            "cartoon": "cartoon style, animated, vibrant colors, 2D illustration",
            "cinematic": "cinematic, film still, dramatic lighting, high production value",
            "realistic": "photorealistic, highly detailed, 8k resolution, professional photography",
            "funny": "humorous, comedic, exaggerated expressions, playful",
            "dramatic": "dramatic, intense, emotional, cinematic lighting",
            "minimal": "minimalist, clean, simple, elegant, modern",
        }
        
        modifier = style_modifiers.get(style, style_modifiers["cinematic"])
        
        enhanced = f"{prompt}, {modifier}, high quality, detailed"
        
        if character_consistency:
            enhanced += f", {character_consistency}"
        
        return enhanced
    
    async def _call_huggingface_api(
        self,
        prompt: str,
        negative_prompt: str,
    ) -> bytes:
        """Call Hugging Face Inference API for image generation."""
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": negative_prompt,
                "num_inference_steps": 50,
                "guidance_scale": 7.5,
                "width": 512,
                "height": 768,
            },
        }
        
        model_url = f"{self.api_url}/{self.model}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                model_url,
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            
            # Response is image bytes
            return response.content
    
    async def _process_and_upload(
        self,
        image_data: bytes,
        aspect_ratio: str,
    ) -> str:
        """Process image and upload to storage."""
        
        # Open image
        image = Image.open(io.BytesIO(image_data))
        
        # Resize to target aspect ratio
        image = self._resize_to_aspect_ratio(image, aspect_ratio)
        
        # Convert to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        # Save to buffer
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)
        
        # Generate filename
        filename = f"images/{uuid.uuid4()}.jpg"
        
        # Upload to storage
        url = await self.storage.upload_file(
            file_data=buffer.getvalue(),
            filename=filename,
            content_type="image/jpeg",
        )
        
        return url
    
    def _resize_to_aspect_ratio(
        self,
        image: Image.Image,
        aspect_ratio: str,
    ) -> Image.Image:
        """Resize image to target aspect ratio."""
        
        ratios = {
            "16:9": (16, 9),
            "9:16": (9, 16),
            "1:1": (1, 1),
        }
        
        target_w, target_h = ratios.get(aspect_ratio, (9, 16))
        target_ratio = target_w / target_h
        
        current_w, current_h = image.size
        current_ratio = current_w / current_h
        
        if current_ratio > target_ratio:
            # Image is wider, crop width
            new_w = int(current_h * target_ratio)
            left = (current_w - new_w) // 2
            image = image.crop((left, 0, left + new_w, current_h))
        else:
            # Image is taller, crop height
            new_h = int(current_w / target_ratio)
            top = (current_h - new_h) // 2
            image = image.crop((0, top, current_w, top + new_h))
        
        # Resize to standard resolution
        resolutions = {
            "16:9": (1920, 1080),
            "9:16": (1080, 1920),
            "1:1": (1080, 1080),
        }
        
        target_size = resolutions.get(aspect_ratio, (1080, 1920))
        image = image.resize(target_size, Image.Resampling.LANCZOS)
        
        return image
    
    def _generate_placeholder_image(self, aspect_ratio: str) -> bytes:
        """Generate placeholder image for development."""
        
        resolutions = {
            "16:9": (1920, 1080),
            "9:16": (1080, 1920),
            "1:1": (1080, 1080),
        }
        
        width, height = resolutions.get(aspect_ratio, (1080, 1920))
        
        # Create gradient image
        image = Image.new('RGB', (width, height), color='#1a1a2e')
        
        # Add some visual elements
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        
        # Draw gradient-like rectangles
        for i in range(0, height, 50):
            color_value = int(26 + (i / height) * 50)
            draw.rectangle([0, i, width, i + 50], fill=(color_value, color_value, color_value + 20))
        
        # Save to buffer
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        buffer.seek(0)
        
        return buffer.getvalue()
    
    async def _get_placeholder_url(self, aspect_ratio: str) -> str:
        """Get placeholder image URL."""
        image_data = self._generate_placeholder_image(aspect_ratio)
        
        filename = f"images/placeholder_{aspect_ratio.replace(':', '_')}_{uuid.uuid4()}.jpg"
        
        url = await self.storage.upload_file(
            file_data=image_data,
            filename=filename,
            content_type="image/jpeg",
        )
        
        return url
    
    async def generate_character_reference(
        self,
        description: str,
        style: str = "cinematic",
    ) -> str:
        """Generate character reference image for consistency."""
        
        prompt = f"Character reference sheet: {description}, multiple angles, consistent appearance"
        
        return await self.generate_image(prompt, style, aspect_ratio="1:1")
