"""
Image generation service — FIXED.
FILE: app/services/ai/image_generation.py

BUGS FIXED:
1. `from app.config import settings` at module level caused circular
   import crash on startup. Moved to lazy import inside __init__.

2. Pollinations.ai (no API key needed) added as first provider —
   always works even when HuggingFace is down or rate-limited.

3. Segmind added as second provider (200 free/month, best quality).

4. HuggingFace kept as third provider with correct aspect-ratio
   dimensions and fixed wait_for_model logic.

5. Placeholder image now only used as absolute last resort.

6. FIX: Added asyncio.sleep between requests to avoid Pollinations 429.

7. FIX: Updated HuggingFace to use new router endpoint
   (https://router.huggingface.co/hf-inference/models/) —
   old api-inference.huggingface.co returns 410 Gone for all image models.

8. FIX: Pollinations 500 — when flux model fails, retry with 'turbo' model.

9. FIX: CRITICAL — When Cloudinary upload fails, return the direct
   Pollinations URL instead of a placeholder. Video always gets real images.
"""

import asyncio
import base64
import io
import uuid
from typing import Optional, Tuple

import httpx
from PIL import Image

from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)

# FIX 7 — use new HF router endpoint models
_HF_IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "Lykon/dreamshaper-8",
    "runwayml/stable-diffusion-v1-5",
]

_API_DIMENSIONS = {
    "9:16":  {"width": 512,  "height": 768},
    "16:9":  {"width": 768,  "height": 512},
    "1:1":   {"width": 512,  "height": 512},
}

_RESOLUTIONS = {
    "9:16":  (720,  1280),
    "16:9":  (1280, 720),
    "1:1":   (720,  720),
}

_PICSUM_SIZES = {
    "9:16":  "720/1280",
    "16:9":  "1280/720",
    "1:1":   "720/720",
}


class ImageGenerationService:

    def __init__(self):
        # FIX 1 — lazy import to avoid circular import crash
        from app.config import get_settings
        s = get_settings()
        self.hf_key      = getattr(s, "HUGGINGFACE_API_KEY", None) or ""
        self.segmind_key = getattr(s, "SEGMIND_API_KEY",    None) or ""
        # FIX 7 — new HF router endpoint
        self.hf_base     = "https://router.huggingface.co/hf-inference/models"
        self.storage     = StorageService()
        self._request_count = 0   # FIX 6 — track for rate limiting

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    async def generate_image(
        self,
        prompt: str,
        style: str                           = "cinematic",
        aspect_ratio: str                    = "9:16",
        negative_prompt: Optional[str]       = None,
        character_consistency: Optional[str] = None,
    ) -> str:
        enhanced = self._enhance_prompt(prompt, style, character_consistency)
        neg      = negative_prompt or (
            "blurry, low quality, distorted, deformed, ugly, "
            "duplicate, watermark, signature, text, nsfw"
        )

        self._request_count += 1
        image_data:  Optional[bytes] = None
        direct_url:  Optional[str]   = None  # FIX 9

        # FIX 6 — delay to avoid rate limits across 10 scenes
        if self._request_count > 1:
            delay = 3.0 if self._request_count % 2 == 0 else 1.5
            await asyncio.sleep(delay)

        # ── Provider 1: Pollinations ──────────────────────────────────────────
        try:
            image_data, direct_url = await self._pollinations(enhanced, aspect_ratio)
        except Exception as e:
            logger.warning(f"Pollinations failed: {e}")
            # FIX 8 — retry with turbo on 500/429
            if "500" in str(e) or "429" in str(e):
                wait = 8.0 if "429" in str(e) else 3.0
                await asyncio.sleep(wait)
                try:
                    image_data, direct_url = await self._pollinations(
                        enhanced, aspect_ratio, model="turbo"
                    )
                except Exception as e2:
                    logger.warning(f"Pollinations turbo retry failed: {e2}")

        # ── Provider 2: Segmind ───────────────────────────────────────────────
        if not image_data and self.segmind_key:
            try:
                image_data = await self._segmind(enhanced, neg, aspect_ratio)
            except Exception as e:
                logger.warning(f"Segmind failed: {e}")

        # ── Provider 3: HuggingFace ───────────────────────────────────────────
        if not image_data and self.hf_key:
            for model in _HF_IMAGE_MODELS:
                try:
                    image_data = await self._huggingface(enhanced, neg, model, aspect_ratio)
                    if image_data:
                        break
                except Exception as e:
                    logger.warning(f"HF {model} failed: {e}")

        # ── Upload to storage ─────────────────────────────────────────────────
        if image_data:
            try:
                url = await self._upload(image_data, aspect_ratio)
                # Only return if it's a real URL, not a placeholder
                if url and "placehold" not in url and url.startswith("http"):
                    return url
            except Exception as e:
                logger.error(f"Image upload failed: {e}")

            # FIX 9 — upload failed but Pollinations gave us a real URL
            if direct_url:
                logger.warning("Storage upload failed — using direct provider URL")
                return direct_url

        # ── Absolute fallback ─────────────────────────────────────────────────
        logger.warning("All image providers failed — using picsum fallback")
        return self._picsum_url(aspect_ratio)

    # ── PROVIDERS ─────────────────────────────────────────────────────────────

    async def _pollinations(
        self,
        prompt: str,
        aspect_ratio: str,
        model: str = "flux",
    ) -> Tuple[bytes, str]:
        """
        FIX 9 — returns (image_bytes, direct_url) so callers can
        use the URL directly if Cloudinary upload fails.
        FIX 8 — model param lets us retry with 'turbo' on 500.
        """
        w, h = _RESOLUTIONS.get(aspect_ratio, (720, 1280))
        import urllib.parse
        encoded = urllib.parse.quote(prompt[:400])
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={w}&height={h}&nologo=true&enhance=true&model={model}"
        )
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as c:
            r = await c.get(url)
            r.raise_for_status()
            if len(r.content) < 1000:
                raise ValueError("Pollinations returned too-small response")
            return r.content, url

    async def _segmind(
        self, prompt: str, neg: str, aspect_ratio: str
    ) -> Optional[bytes]:
        """Segmind SDXL — 200 free/month, best quality."""
        dims = _API_DIMENSIONS.get(aspect_ratio, _API_DIMENSIONS["9:16"])
        payload = {
            "prompt":              prompt,
            "negative_prompt":     neg,
            "style":               "hdr",
            "samples":             1,
            "num_inference_steps": 30,
            "guidance_scale":      7.5,
            "width":               dims["width"]  * 2,
            "height":              dims["height"] * 2,
            "base64":              False,
        }
        headers = {
            "x-api-key":    self.segmind_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=90.0) as c:
            r = await c.post(
                "https://api.segmind.com/v1/sdxl1.0-txt2img",
                headers=headers,
                json=payload,
            )
        if r.status_code == 402:
            logger.warning("Segmind quota exhausted")
            return None
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "image" in ct or "octet-stream" in ct:
            return r.content
        data = r.json()
        b64  = data.get("image") or data.get("output")
        if b64:
            return base64.b64decode(b64)
        return None

    async def _huggingface(
        self,
        prompt: str, neg: str,
        model: str, aspect_ratio: str,
    ) -> bytes:
        """
        FIX 7 — New HF router endpoint.
        Old: api-inference.huggingface.co/models/ → 410 Gone
        New: router.huggingface.co/hf-inference/models/
        """
        dims    = _API_DIMENSIONS.get(aspect_ratio, _API_DIMENSIONS["9:16"])
        headers = {
            "Authorization": f"Bearer {self.hf_key}",
            "Content-Type":  "application/json",
        }
        is_flux = "flux" in model.lower() or "schnell" in model.lower()
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt":     neg,
                "num_inference_steps": 4 if is_flux else 28,
                "guidance_scale":      0.0 if is_flux else 7.0,
                "width":               dims["width"],
                "height":              dims["height"],
            },
            "options": {"wait_for_model": True, "use_cache": False},
        }
        async with httpx.AsyncClient(timeout=90.0) as c:
            r = await c.post(
                f"{self.hf_base}/{model}",
                headers=headers,
                json=payload,
            )
        if r.status_code == 503:
            raise RuntimeError("HF model loading (503)")
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "application/json" in ct:
            err = r.json()
            raise RuntimeError(f"HF error: {err.get('error', str(err))[:100]}")
        return r.content

    # ── POST-PROCESSING ───────────────────────────────────────────────────────

    async def _upload(self, image_data: bytes, aspect_ratio: str) -> str:
        image = Image.open(io.BytesIO(image_data))
        image = self._crop_to_ratio(image, aspect_ratio)
        if image.mode != "RGB":
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=88)
        buf.seek(0)
        return await self.storage.upload_file(
            file_data=buf.getvalue(),
            filename=f"images/{uuid.uuid4()}.jpg",
            content_type="image/jpeg",
        )

    def _crop_to_ratio(self, image: Image.Image, aspect_ratio: str) -> Image.Image:
        ratios = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1)}
        tw, th = ratios.get(aspect_ratio, (9, 16))
        tr     = tw / th
        w, h   = image.size
        cr     = w / h
        if cr > tr:
            nw = int(h * tr)
            image = image.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / tr)
            image = image.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        rw, rh = _RESOLUTIONS.get(aspect_ratio, (720, 1280))
        return image.resize((rw, rh), Image.Resampling.LANCZOS)

    def _enhance_prompt(
        self,
        prompt: str,
        style: str,
        character_consistency: Optional[str],
    ) -> str:
        MODS = {
            "cartoon":   "cartoon style, vibrant, animated, Disney/Pixar quality",
            "cinematic": "cinematic film still, dramatic lighting, movie quality",
            "realistic": "photorealistic, professional photography, sharp focus, 8K",
            "funny":     "comedic, exaggerated, playful, vibrant colors",
            "dramatic":  "dramatic, intense, moody cinematic lighting",
            "minimal":   "minimalist, clean, elegant, soft lighting",
        }
        mod   = MODS.get(style, MODS["realistic"])
        base  = f"{prompt.strip()}, {mod}, high quality, 4K"
        if character_consistency:
            base += f", {character_consistency}, consistent appearance"
        return base

    def _placeholder(self, aspect_ratio: str) -> bytes:
        w, h = _RESOLUTIONS.get(aspect_ratio, (720, 1280))
        img  = Image.new("RGB", (w, h), color=(26, 26, 46))
        buf  = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        buf.seek(0)
        return buf.getvalue()

    def _placeholder_url(self, aspect_ratio: str) -> str:
        URLs = {
            "9:16": "https://placehold.co/720x1280/1a1a2e/ffffff?text=chAs+AI",
            "16:9": "https://placehold.co/1280x720/1a1a2e/ffffff?text=chAs+AI",
            "1:1":  "https://placehold.co/720x720/1a1a2e/ffffff?text=chAs+AI",
        }
        return URLs.get(aspect_ratio, URLs["9:16"])

    def _picsum_url(self, aspect_ratio: str) -> str:
        """Real photo fallback when all providers and storage fail."""
        size = _PICSUM_SIZES.get(aspect_ratio, "720/1280")
        seed = uuid.uuid4().int % 1000
        return f"https://picsum.photos/seed/{seed}/{size}"

    async def generate_character_reference(
        self, description: str, style: str = "cinematic"
    ) -> str:
        prompt = (
            f"Character reference: {description}, "
            "front view, side view, consistent look, white background"
        )
        return await self.generate_image(prompt, style, "1:1")
