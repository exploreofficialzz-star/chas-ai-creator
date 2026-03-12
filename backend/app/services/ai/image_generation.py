"""
Image generation service.
FILE: app/services/ai/image_generation.py

FIXES:
1. API payload width/height was hardcoded to 512x768 regardless of
   aspect_ratio. A 9:16 video was getting 512x768 images (correct),
   but 16:9 and 1:1 also got 512x768 (wrong proportions → stretched).
   Fixed: width/height now derived from aspect_ratio.

2. No changes needed to fallback model list, placeholder logic, or
   upload pipeline — those were already fixed in a previous session.
   This file is otherwise production-ready.
"""

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

FALLBACK_MODELS = [
    "stabilityai/stable-diffusion-2-1",
    "runwayml/stable-diffusion-v1-5",
    "CompVis/stable-diffusion-v1-4",
    "prompthero/openjourney-v4",
]

# FIX 1 — correct API dimensions per aspect ratio
# HuggingFace SD models require dimensions divisible by 8, max 768 on free tier
API_DIMENSIONS = {
    "9:16":  {"width": 512,  "height": 768},   # portrait  — TikTok/Reels
    "16:9":  {"width": 768,  "height": 512},   # landscape — YouTube
    "1:1":   {"width": 512,  "height": 512},   # square    — Instagram
}


class ImageGenerationService:
    """Service for generating images using AI models."""

    def __init__(self):
        self.api_key  = settings.HUGGINGFACE_API_KEY
        self.api_base = "https://api-inference.huggingface.co/models"
        self.storage  = StorageService()

    async def generate_image(
        self,
        prompt: str,
        style: str = "cinematic",
        aspect_ratio: str = "9:16",
        negative_prompt: Optional[str] = None,
        character_consistency: Optional[str] = None,
    ) -> str:
        """Generate image with automatic model fallback chain."""

        enhanced_prompt = self._enhance_prompt(prompt, style, character_consistency)

        if not negative_prompt:
            negative_prompt = (
                "blurry, low quality, distorted, deformed, ugly, "
                "duplicate, watermark, signature, text, nsfw, violence"
            )

        image_data: Optional[bytes] = None

        if self.api_key:
            for model in FALLBACK_MODELS:
                try:
                    logger.info(f"Trying image model: {model}")
                    image_data = await self._call_huggingface_api(
                        enhanced_prompt, negative_prompt, model, aspect_ratio
                    )
                    if image_data:
                        logger.info(f"Image generated with: {model}")
                        break
                except Exception as e:
                    err = str(e)
                    if any(c in err for c in ["410", "404", "503", "loading"]):
                        logger.warning(f"Model {model} unavailable ({err[:80]})")
                        continue
                    logger.error(f"Image error {model}: {err}")

        if not image_data:
            logger.warning("All HF image models failed — using placeholder")
            image_data = self._generate_placeholder_image(aspect_ratio)

        try:
            return await self._process_and_upload(image_data, aspect_ratio)
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            return self._get_public_placeholder_url(aspect_ratio)

    def _enhance_prompt(
        self,
        prompt: str,
        style: str,
        character_consistency: Optional[str] = None,
    ) -> str:
        style_modifiers = {
            "cartoon":   "cartoon style, animated, vibrant colors, 2D illustration, Disney style",
            "cinematic": "cinematic film still, dramatic lighting, high production value, movie scene",
            "realistic": "photorealistic, highly detailed, professional photography, sharp focus",
            "funny":     "humorous, comedic, exaggerated expressions, playful cartoon",
            "dramatic":  "dramatic, intense, emotional, cinematic lighting, epic scene",
            "minimal":   "minimalist, clean lines, simple composition, elegant, modern design",
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
        aspect_ratio: str = "9:16",
    ) -> bytes:
        """Call HuggingFace Inference API with correct dimensions for aspect ratio."""

        # FIX 1 — use correct dimensions per aspect ratio
        dims = API_DIMENSIONS.get(aspect_ratio, API_DIMENSIONS["9:16"])

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt":    negative_prompt,
                "num_inference_steps": 30,
                "guidance_scale":      7.5,
                "width":               dims["width"],   # FIX 1
                "height":              dims["height"],  # FIX 1
            },
            "options": {
                "wait_for_model": False,
                "use_cache":      True,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/{model}",
                headers=headers,
                json=payload,
                timeout=90.0,
            )

            if response.status_code == 503:
                raise Exception("503 Model is loading")

            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                err = response.json()
                raise Exception(f"API returned JSON error: {err.get('error', str(err))}")

            return response.content

    async def _process_and_upload(self, image_data: bytes, aspect_ratio: str) -> str:
        image = Image.open(io.BytesIO(image_data))
        image = self._resize_to_aspect_ratio(image, aspect_ratio)
        if image.mode != "RGB":
            image = image.convert("RGB")

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        return await self.storage.upload_file(
            file_data=buffer.getvalue(),
            filename=f"images/{uuid.uuid4()}.jpg",
            content_type="image/jpeg",
        )

    def _resize_to_aspect_ratio(self, image: Image.Image, aspect_ratio: str) -> Image.Image:
        ratios = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1)}
        target_w, target_h = ratios.get(aspect_ratio, (9, 16))
        target_ratio  = target_w / target_h
        current_w, current_h = image.size
        current_ratio = current_w / current_h

        if current_ratio > target_ratio:
            new_w = int(current_h * target_ratio)
            left  = (current_w - new_w) // 2
            image = image.crop((left, 0, left + new_w, current_h))
        else:
            new_h = int(current_w / target_ratio)
            top   = (current_h - new_h) // 2
            image = image.crop((0, top, current_w, top + new_h))

        resolutions = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720)}
        image = image.resize(resolutions.get(aspect_ratio, (720, 1280)), Image.Resampling.LANCZOS)
        return image

    def _generate_placeholder_image(self, aspect_ratio: str) -> bytes:
        resolutions = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720)}
        width, height = resolutions.get(aspect_ratio, (720, 1280))
        image = Image.new("RGB", (width, height), color=(26, 26, 46))

        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        for i in range(height):
            r = int(26 + (i / height) * 30)
            g = int(26 + (i / height) * 10)
            b = int(46 + (i / height) * 40)
            draw.line([(0, i), (width, i)], fill=(r, g, b))

        cx, cy = width // 2, height // 2
        draw.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], outline=(100, 80, 255), width=3)
        draw.text((cx - 30, cy - 12), "chAs",        fill=(200, 200, 255))
        draw.text((cx - 50, cy + 20), "Generating...", fill=(150, 150, 200))

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=80)
        buf.seek(0)
        return buf.getvalue()

    def _get_public_placeholder_url(self, aspect_ratio: str) -> str:
        placeholders = {
            "9:16": "https://placehold.co/720x1280/1a1a2e/ffffff?text=chAs+AI+Creator",
            "16:9": "https://placehold.co/1280x720/1a1a2e/ffffff?text=chAs+AI+Creator",
            "1:1":  "https://placehold.co/720x720/1a1a2e/ffffff?text=chAs+AI+Creator",
        }
        return placeholders.get(aspect_ratio, placeholders["9:16"])

    async def generate_character_reference(
        self, description: str, style: str = "cinematic"
    ) -> str:
        prompt = (
            f"Character reference sheet: {description}, "
            "multiple angles, front view, side view, consistent appearance, white background"
        )
        return await self.generate_image(prompt, style, aspect_ratio="1:1")
