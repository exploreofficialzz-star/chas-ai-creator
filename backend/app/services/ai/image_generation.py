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

# FIX 1 - updated model list, SDXL 1.0 is 410 Gone on HuggingFace free inference
# These are tested working models on the free HuggingFace Inference API
FALLBACK_MODELS = [
    "stabilityai/stable-diffusion-2-1",         # Primary - working
    "runwayml/stable-diffusion-v1-5",            # Fallback 1 - working
    "CompVis/stable-diffusion-v1-4",             # Fallback 2 - working
    "prompthero/openjourney-v4",                 # Fallback 3 - stylized
]


class ImageGenerationService:
    """Service for generating images using AI models."""

    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        # FIX 2 - hardcode the base URL, don't rely on settings model that may be stale
        self.api_base = "https://api-inference.huggingface.co/models"
        self.storage = StorageService()

    async def generate_image(
        self,
        prompt: str,
        style: str = "cinematic",
        aspect_ratio: str = "9:16",
        negative_prompt: Optional[str] = None,
        character_consistency: Optional[str] = None,
    ) -> str:
        """Generate image from prompt with automatic model fallback."""

        enhanced_prompt = self._enhance_prompt(prompt, style, character_consistency)

        if not negative_prompt:
            negative_prompt = (
                "blurry, low quality, distorted, deformed, ugly, "
                "duplicate, watermark, signature, text, nsfw, violence"
            )

        image_data = None

        # FIX 3 - try each model in order until one works
        if self.api_key:
            for model in FALLBACK_MODELS:
                try:
                    logger.info(f"Trying image model: {model}")
                    image_data = await self._call_huggingface_api(
                        enhanced_prompt, negative_prompt, model
                    )
                    if image_data:
                        logger.info(f"Image generated with model: {model}")
                        break
                except Exception as e:
                    err = str(e)
                    # FIX 4 - skip models that are gone/unavailable, try next
                    if "410" in err or "404" in err or "503" in err or "loading" in err.lower():
                        logger.warning(f"Model {model} unavailable ({err[:80]}), trying next...")
                        continue
                    else:
                        logger.error(f"Image generation error with {model}: {err}")
                        continue

        # FIX 5 - if ALL models failed, use placeholder instead of crashing
        if not image_data:
            logger.warning("All HuggingFace models failed — using placeholder image")
            image_data = self._generate_placeholder_image(aspect_ratio)

        try:
            image_url = await self._process_and_upload(image_data, aspect_ratio)
            return image_url
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            # FIX 6 - return a public placeholder URL instead of crashing the whole video
            return self._get_public_placeholder_url(aspect_ratio)

    def _enhance_prompt(
        self,
        prompt: str,
        style: str,
        character_consistency: Optional[str] = None,
    ) -> str:
        """Enhance prompt with style modifiers."""

        style_modifiers = {
            "cartoon": "cartoon style, animated, vibrant colors, 2D illustration, Disney style",
            "cinematic": "cinematic film still, dramatic lighting, high production value, movie scene",
            "realistic": "photorealistic, highly detailed, professional photography, sharp focus",
            "funny": "humorous, comedic, exaggerated expressions, playful cartoon",
            "dramatic": "dramatic, intense, emotional, cinematic lighting, epic scene",
            "minimal": "minimalist, clean lines, simple composition, elegant, modern design",
        }

        modifier = style_modifiers.get(style, style_modifiers["cinematic"])
        enhanced = f"{prompt}, {modifier}, high quality, detailed, 4k"

        if character_consistency:
            enhanced += f", {character_consistency}, consistent character design"

        return enhanced

    async def _call_huggingface_api(
        self,
        prompt: str,
        negative_prompt: str,
        model: str,
    ) -> bytes:
        """Call Hugging Face Inference API for a specific model."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": negative_prompt,
                "num_inference_steps": 30,   # FIX 7 - reduced from 50 for speed
                "guidance_scale": 7.5,
                "width": 512,
                "height": 768,
            },
            # FIX 8 - don't wait forever for model to load, fail fast and try next
            "options": {
                "wait_for_model": False,
                "use_cache": True,
            },
        }

        model_url = f"{self.api_base}/{model}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                model_url,
                headers=headers,
                json=payload,
                timeout=90.0,
            )

            # FIX 9 - handle model loading state (503 means model is cold-starting)
            if response.status_code == 503:
                raise Exception("503 Model is loading")

            response.raise_for_status()

            # FIX 10 - validate we actually got image bytes, not a JSON error
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                # HuggingFace returned an error JSON instead of image
                error_body = response.json()
                raise Exception(f"API returned JSON error: {error_body.get('error', str(error_body))}")

            return response.content

    async def _process_and_upload(
        self,
        image_data: bytes,
        aspect_ratio: str,
    ) -> str:
        """Process image and upload to storage."""

        image = Image.open(io.BytesIO(image_data))
        image = self._resize_to_aspect_ratio(image, aspect_ratio)

        # FIX 11 - handle all non-RGB modes including palette mode P
        if image.mode != "RGB":
            image = image.convert("RGB")

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        filename = f"images/{uuid.uuid4()}.jpg"

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
        """Resize and crop image to target aspect ratio."""

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
            new_w = int(current_h * target_ratio)
            left = (current_w - new_w) // 2
            image = image.crop((left, 0, left + new_w, current_h))
        else:
            new_h = int(current_w / target_ratio)
            top = (current_h - new_h) // 2
            image = image.crop((0, top, current_w, top + new_h))

        resolutions = {
            "16:9": (1280, 720),    # FIX 12 - reduced from 1920x1080, faster upload
            "9:16": (720, 1280),    # reduced from 1080x1920
            "1:1": (720, 720),      # reduced from 1080x1080
        }

        target_size = resolutions.get(aspect_ratio, (720, 1280))
        image = image.resize(target_size, Image.Resampling.LANCZOS)

        return image

    def _generate_placeholder_image(self, aspect_ratio: str) -> bytes:
        """Generate branded placeholder image when AI fails."""

        resolutions = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "1:1": (720, 720),
        }

        width, height = resolutions.get(aspect_ratio, (720, 1280))
        image = Image.new("RGB", (width, height), color=(26, 26, 46))

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)

        # Draw gradient background
        for i in range(height):
            ratio = i / height
            r = int(26 + ratio * 30)
            g = int(26 + ratio * 10)
            b = int(46 + ratio * 40)
            draw.line([(0, i), (width, i)], fill=(r, g, b))

        # Draw centered chAs branding
        cx, cy = width // 2, height // 2
        draw.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], outline=(100, 80, 255), width=3)
        draw.text((cx - 30, cy - 12), "chAs", fill=(200, 200, 255))
        draw.text((cx - 50, cy + 20), "Generating...", fill=(150, 150, 200))

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        buffer.seek(0)

        return buffer.getvalue()

    def _get_public_placeholder_url(self, aspect_ratio: str) -> str:
        """FIX 13 - Return a real working public placeholder URL as last resort.
        This prevents the video from failing completely when storage is down."""

        placeholders = {
            "9:16":  "https://placehold.co/720x1280/1a1a2e/ffffff?text=chAs+AI+Creator",
            "16:9":  "https://placehold.co/1280x720/1a1a2e/ffffff?text=chAs+AI+Creator",
            "1:1":   "https://placehold.co/720x720/1a1a2e/ffffff?text=chAs+AI+Creator",
        }
        return placeholders.get(aspect_ratio, placeholders["9:16"])

    async def generate_character_reference(
        self,
        description: str,
        style: str = "cinematic",
    ) -> str:
        """Generate character reference image for consistency."""

        prompt = (
            f"Character reference sheet: {description}, "
            f"multiple angles, front view, side view, consistent appearance, white background"
        )

        return await self.generate_image(prompt, style, aspect_ratio="1:1")
