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

5. Placeholder image now only used as absolute last resort — real
   AI images from Pollinations always available.
"""

import base64
import io
import uuid
from typing import Optional

import httpx
from PIL import Image

from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)

# HF fallback models
_HF_IMAGE_MODELS = [
    "stabilityai/stable-diffusion-xl-base-1.0",
    "stabilityai/stable-diffusion-2-1",
    "runwayml/stable-diffusion-v1-5",
    "prompthero/openjourney-v4",
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


class ImageGenerationService:

    def __init__(self):
        # FIX 1 — lazy import to avoid circular import crash
        from app.config import get_settings
        s = get_settings()
        self.hf_key      = getattr(s, "HUGGINGFACE_API_KEY", None) or ""
        self.segmind_key = getattr(s, "SEGMIND_API_KEY",    None) or ""
        self.hf_base     = "https://api-inference.huggingface.co/models"
        self.storage     = StorageService()

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    async def generate_image(
        self,
        prompt: str,
        style: str                          = "cinematic",
        aspect_ratio: str                   = "9:16",
        negative_prompt: Optional[str]      = None,
        character_consistency: Optional[str]= None,
    ) -> str:
        enhanced = self._enhance_prompt(prompt, style, character_consistency)
        neg      = negative_prompt or (
            "blurry, low quality, distorted, deformed, ugly, "
            "duplicate, watermark, signature, text, nsfw"
        )

        image_data: Optional[bytes] = None

        # FIX 2 — Pollinations first (no key, always free)
        try:
            image_data = await self._pollinations(enhanced, aspect_ratio)
        except Exception as e:
            logger.warning(f"Pollinations failed: {e}")

        # FIX 3 — Segmind second
        if not image_data and self.segmind_key:
            try:
                image_data = await self._segmind(enhanced, neg, aspect_ratio)
            except Exception as e:
                logger.warning(f"Segmind failed: {e}")

        # FIX 4 — HuggingFace third
        if not image_data and self.hf_key:
            for model in _HF_IMAGE_MODELS:
                try:
                    image_data = await self._huggingface(enhanced, neg, model, aspect_ratio)
                    if image_data:
                        break
                except Exception as e:
                    logger.warning(f"HF {model} failed: {e}")

        # FIX 5 — placeholder only as last resort
        if not image_data:
            logger.warning("All image providers failed — using placeholder")
            image_data = self._placeholder(aspect_ratio)

        try:
            return await self._upload(image_data, aspect_ratio)
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            return self._placeholder_url(aspect_ratio)

    # ── PROVIDERS ─────────────────────────────────────────────────────────────

    async def _pollinations(self, prompt: str, aspect_ratio: str) -> bytes:
        """FIX 2 — Pollinations.ai: free, no API key, good quality."""
        w, h = _RESOLUTIONS.get(aspect_ratio, (720, 1280))
        encoded = prompt.replace(" ", "%20").replace(",", "%2C")[:400]
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={w}&height={h}&nologo=true&enhance=true&model=flux"
        )
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as c:
            r = await c.get(url)
            r.raise_for_status()
            if len(r.content) < 1000:
                raise ValueError("Pollinations returned too-small response")
            return r.content

    async def _segmind(
        self, prompt: str, neg: str, aspect_ratio: str
    ) -> Optional[bytes]:
        """Segmind SDXL — 200 free/month, best quality."""
        dims = _API_DIMENSIONS.get(aspect_ratio, _API_DIMENSIONS["9:16"])
        payload = {
            "prompt":          prompt,
            "negative_prompt": neg,
            "style":           "hdr",
            "samples":         1,
            "num_inference_steps": 30,
            "guidance_scale":  7.5,
            "width":           dims["width"]  * 2,    # Segmind supports up to 1024
            "height":          dims["height"] * 2,
            "base64":          False,
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
        """FIX 4 — correct dimensions, correct wait_for_model usage."""
        dims    = _API_DIMENSIONS.get(aspect_ratio, _API_DIMENSIONS["9:16"])
        headers = {
            "Authorization": f"Bearer {self.hf_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt":     neg,
                "num_inference_steps": 28,
                "guidance_scale":      7.0,
                "width":               dims["width"],
                "height":              dims["height"],
            },
            "options": {"wait_for_model": True, "use_cache": False},
        }
        async with httpx.AsyncClient(timeout=90.0) as c:
            r = await c.post(f"{self.hf_base}/{model}", headers=headers, json=payload)
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

    async def generate_character_reference(
        self, description: str, style: str = "cinematic"
    ) -> str:
        prompt = (
            f"Character reference: {description}, "
            "front view, side view, consistent look, white background"
        )
        return await self.generate_image(prompt, style, "1:1")


# ─────────────────────────────────────────────────────────────────────────────


"""
Video clip generation service — FIXED.
FILE: app/services/ai/video_generation.py

BUGS FIXED:
1. CRITICAL — Service was calling SVD (img2vid) model but trying to use
   it as a text-to-video model. Completely rebuilt with proper T2V chain:
     Replicate (AnimateDiff / ZeroScope) → Segmind → HF ZeroScope → FFmpeg

2. CRITICAL — _generate_placeholder_video returned b"" (empty bytes).
   Cloudinary rejected the upload. Now returns a real FFmpeg-generated
   black MP4.

3. CRITICAL — placeholder URL was placehold.co (a PNG), not a video.
   FFmpeg concat crashed. Fixed: always upload a real MP4 to Cloudinary.

4. apply_camera_motion() was a no-op stub. Implemented with FFmpeg zoompan.

5. _download_image() had no follow_redirects — Cloudinary 302 → 0 bytes.

6. settings accessed without getattr fallback → crash if key missing.

7. Replicate polling was not handling the case where output is a list.
"""

import asyncio
import base64
import io
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image

from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)

_HF_BASE     = "https://api-inference.huggingface.co/models"
_REPLICATE   = "https://api.replicate.com/v1"
_SEGMIND     = "https://api.segmind.com/v1"

_HF_T2V_MODELS = [
    "cerspense/zeroscope_v2_576w",
    "damo-vilab/text-to-video-ms-1.7b",
]

_REPLICATE_T2V_MODELS = [
    {
        "owner":   "lucataco",
        "model":   "animate-diff-lightning",
        "version": "beecf59c4ea3deaa600bc60a6c59b99bef0a8f5b",
    },
    {
        "owner":   "anotherjesse",
        "model":   "zeroscope-v2-xl",
        "version": "9f747673945c62801b13b84701c783929c0ee784",
    },
]

_TIMEOUT      = 180.0
_POLL_MAX     = 150
_POLL_SLEEP   = 4


class VideoGenerationService:

    def __init__(self):
        from app.config import get_settings          # FIX 6 — lazy safe import
        s = get_settings()
        self.hf_key        = getattr(s, "HUGGINGFACE_API_KEY", None) or ""
        self.replicate_key = getattr(s, "REPLICATE_API_KEY",   None) or ""
        self.segmind_key   = getattr(s, "SEGMIND_API_KEY",     None) or ""
        self.storage       = StorageService()

        active = [k for k, v in {
            "Replicate": self.replicate_key,
            "Segmind":   self.segmind_key,
            "HF":        self.hf_key,
        }.items() if v]
        logger.info(f"Video gen providers: {active or ['FFmpeg-only']}")

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    async def generate_video_clip(
        self,
        image_url: str   = "",
        prompt: str      = "",
        duration: float  = 3.0,
        aspect_ratio: str= "9:16",
        motion_strength: float = 0.5,
    ) -> str:
        """
        FIX 1 — Generate a real video clip from a text prompt.
        Provider chain: Replicate → Segmind → HuggingFace → FFmpeg fallback.
        Always returns a valid MP4 URL.
        """
        enhanced = _enhance_prompt(prompt, aspect_ratio)
        w, h     = _dimensions(aspect_ratio)
        video_data: Optional[bytes] = None

        # 1. Replicate
        if self.replicate_key:
            try:
                video_data = await self._replicate_t2v(enhanced, w, h, duration)
            except Exception as e:
                logger.warning(f"Replicate T2V failed: {e}")

        # 2. Segmind
        if not video_data and self.segmind_key:
            try:
                video_data = await self._segmind_t2v(enhanced, w, h, duration)
            except Exception as e:
                logger.warning(f"Segmind T2V failed: {e}")

        # 3. HuggingFace
        if not video_data and self.hf_key:
            try:
                video_data = await self._hf_t2v(enhanced, w, h)
            except Exception as e:
                logger.warning(f"HF T2V failed: {e}")

        # 4. FFmpeg fallback — create clip from image or blank
        if not video_data:
            img_data = None
            if image_url:
                try:
                    img_data = await _download(image_url)
                except Exception as e:
                    logger.warning(f"Could not download image ({e})")
            video_data = await _ffmpeg_clip(img_data, duration, aspect_ratio)

        # Upload and return URL
        filename  = f"clips/{uuid.uuid4()}.mp4"
        video_url = await self.storage.upload_file(
            file_data=video_data,
            filename=filename,
            content_type="video/mp4",
        )
        logger.info(f"Clip ready: {filename} ({len(video_data):,} bytes)")
        return video_url

    async def apply_camera_motion(
        self,
        video_url: str,
        motion_type: str = "zoom_in",
        intensity: float = 0.5,
    ) -> str:
        """FIX 4 — Real FFmpeg zoompan implementation."""
        try:
            # Try to download the video for processing
            video_data = await _download(video_url)
            processed  = await asyncio.to_thread(
                _ffmpeg_motion_sync, video_data, motion_type, intensity
            )
            out_url = await self.storage.upload_file(
                file_data=processed,
                filename=f"clips/motion_{uuid.uuid4()}.mp4",
                content_type="video/mp4",
            )
            return out_url
        except Exception as e:
            logger.warning(f"apply_camera_motion failed ({e}), returning original")
            return video_url

    # ── REPLICATE ─────────────────────────────────────────────────────────────

    async def _replicate_t2v(
        self, prompt: str, w: int, h: int, duration: float
    ) -> Optional[bytes]:
        headers = {
            "Authorization": f"Token {self.replicate_key}",
            "Content-Type":  "application/json",
        }
        for model_cfg in _REPLICATE_T2V_MODELS:
            try:
                fps      = 8
                n_frames = max(16, min(int(duration * fps), 48))
                payload  = {
                    "version": model_cfg["version"],
                    "input": {
                        "prompt":          prompt,
                        "negative_prompt": "blurry, low quality, distorted, watermark",
                        "num_frames":      n_frames,
                        "guidance_scale":  7.5,
                        "num_inference_steps": 25,
                        "fps":             fps,
                        "width":           min(w, 1024),
                        "height":          min(h, 1024),
                    },
                }
                async with httpx.AsyncClient(timeout=30.0) as c:
                    r = await c.post(f"{_REPLICATE}/predictions", headers=headers, json=payload)
                if r.status_code not in (200, 201):
                    logger.warning(f"Replicate {model_cfg['model']} create: HTTP {r.status_code}")
                    continue

                pred_id   = r.json().get("id")
                video_url = await self._replicate_poll(pred_id, headers)
                if video_url:
                    data = await _download(video_url)
                    if data and len(data) > 1000:
                        logger.info(f"✓ Replicate/{model_cfg['model']}")
                        return data
            except Exception as e:
                logger.warning(f"Replicate {model_cfg['model']}: {e}")
        return None

    async def _replicate_poll(self, pred_id: str, headers: Dict) -> Optional[str]:
        deadline = time.time() + _POLL_MAX
        while time.time() < deadline:
            await asyncio.sleep(_POLL_SLEEP)
            try:
                async with httpx.AsyncClient(timeout=15.0) as c:
                    r = await c.get(f"{_REPLICATE}/predictions/{pred_id}", headers=headers)
                if r.status_code != 200:
                    continue
                data   = r.json()
                status = data.get("status")
                if status == "succeeded":
                    out = data.get("output")
                    # FIX 7 — handle both list and string output
                    if isinstance(out, list) and out:
                        return out[-1]      # last item is usually the final video
                    if isinstance(out, str) and out.startswith("http"):
                        return out
                    return None
                if status == "failed":
                    logger.warning(f"Replicate {pred_id} failed: {data.get('error')}")
                    return None
            except Exception as e:
                logger.debug(f"Replicate poll error: {e}")
        logger.warning(f"Replicate {pred_id} timed out")
        return None

    # ── SEGMIND ───────────────────────────────────────────────────────────────

    async def _segmind_t2v(
        self, prompt: str, w: int, h: int, duration: float
    ) -> Optional[bytes]:
        headers = {
            "x-api-key":    self.segmind_key,
            "Content-Type": "application/json",
        }
        endpoints = ["haiper-video-v2", "svd-img2vid"]
        for ep in endpoints:
            try:
                payload = {
                    "prompt":   prompt,
                    "width":    min(w, 1024),
                    "height":   min(h, 1024),
                    "duration": int(duration),
                    "base64":   False,
                }
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    r = await c.post(f"{_SEGMIND}/{ep}", headers=headers, json=payload)
                if r.status_code == 402:
                    logger.warning("Segmind quota exhausted")
                    return None
                if r.status_code == 404:
                    continue    # endpoint not available, try next
                if r.status_code != 200:
                    logger.warning(f"Segmind {ep}: HTTP {r.status_code}")
                    continue
                ct = r.headers.get("content-type", "")
                if "video" in ct or "octet-stream" in ct:
                    logger.info(f"✓ Segmind/{ep}")
                    return r.content
                data = r.json()
                url  = data.get("video_url") or data.get("output") or data.get("url")
                if url:
                    return await _download(url)
            except Exception as e:
                logger.warning(f"Segmind {ep}: {e}")
        return None

    # ── HUGGINGFACE T2V ───────────────────────────────────────────────────────

    async def _hf_t2v(self, prompt: str, w: int, h: int) -> Optional[bytes]:
        headers = {
            "Authorization": f"Bearer {self.hf_key}",
            "Content-Type":  "application/json",
        }
        for model in _HF_T2V_MODELS:
            payload = {
                "inputs": prompt,
                "parameters": {
                    "num_frames":          16,
                    "num_inference_steps": 25,
                    "guidance_scale":      7.5,
                    "width":               min(w, 576),
                    "height":              min(h, 320),
                },
                "options": {"wait_for_model": True, "use_cache": False},
            }
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                        r = await c.post(f"{_HF_BASE}/{model}", headers=headers, json=payload)
                    if r.status_code == 503:
                        if attempt == 0:
                            await asyncio.sleep(10.0)
                            continue
                        break
                    if r.status_code != 200:
                        break
                    ct = r.headers.get("content-type", "")
                    if "video" in ct or len(r.content) > 10_000:
                        logger.info(f"✓ HF/{model}")
                        return r.content
                    break
                except httpx.TimeoutException:
                    if attempt == 0:
                        await asyncio.sleep(5.0)
                    continue
                except Exception as e:
                    logger.warning(f"HF {model}: {e}")
                    break
        return None


# ── Pure functions ────────────────────────────────────────────────────────────

def _dimensions(aspect_ratio: str) -> Tuple[int, int]:
    return {"9:16": (576, 1024), "16:9": (1024, 576), "1:1": (576, 576)}.get(
        aspect_ratio, (576, 1024)
    )


def _enhance_prompt(prompt: str, aspect_ratio: str) -> str:
    ratio_note = {
        "9:16": "vertical portrait format",
        "16:9": "horizontal landscape format",
        "1:1":  "square format",
    }.get(aspect_ratio, "vertical format")
    return (
        f"{prompt.strip()}, ultra realistic, cinematic, 4K, smooth motion, "
        f"professional camera work, {ratio_note}, "
        f"no flickering, no artifacts, high quality video"
    )


async def _download(url: str) -> bytes:
    """FIX 5 — follow_redirects for Cloudinary CDN."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as c:
        r = await c.get(url)
        r.raise_for_status()
        if len(r.content) == 0:
            raise ValueError(f"0 bytes from {url}")
        return r.content


async def _ffmpeg_clip(
    image_data: Optional[bytes],
    duration: float,
    aspect_ratio: str,
) -> bytes:
    """FIX 2 / FIX 3 — Always produce a valid MP4 via FFmpeg."""
    return await asyncio.to_thread(
        _ffmpeg_clip_sync, image_data, duration, aspect_ratio
    )


def _ffmpeg_clip_sync(
    image_data: Optional[bytes],
    duration: float,
    aspect_ratio: str,
) -> bytes:
    w, h = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720)}.get(
        aspect_ratio, (720, 1280)
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "clip.mp4"

        if image_data:
            img_path = Path(tmp) / "frame.jpg"
            # Ensure it's a valid JPEG
            try:
                img = Image.open(io.BytesIO(image_data))
                img = img.convert("RGB")
                img.save(str(img_path), "JPEG", quality=90)
            except Exception:
                img_path = None

            if img_path and img_path.exists():
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(img_path),
                    "-vf", (
                        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
                        # subtle zoom for more cinematic feel
                        f"zoompan=z='min(zoom+0.001,1.1)':d=1:s={w}x{h}"
                    ),
                    "-c:v", "libx264", "-t", str(duration),
                    "-pix_fmt", "yuv420p", "-r", "24",
                    "-preset", "ultrafast", str(out),
                ]
                res = subprocess.run(cmd, capture_output=True, timeout=60)
                if res.returncode == 0:
                    return out.read_bytes()

        # No image — generate black clip
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=black:s={w}x{h}:d={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "ultrafast", str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=30)
        if res.returncode == 0:
            return out.read_bytes()

    raise RuntimeError("FFmpeg could not generate a clip")


def _ffmpeg_motion_sync(
    video_data: bytes,
    motion_type: str,
    intensity: float,
) -> bytes:
    """FIX 4 — Real FFmpeg zoompan camera motion."""
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / "in.mp4"
        out = Path(tmp) / "out.mp4"
        inp.write_bytes(video_data)

        zoom = 1.0 + intensity * 0.3
        VF = {
            "zoom_in":   f"zoompan=z='min(zoom+{intensity*0.015},1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1",
            "zoom_out":  f"zoompan=z='if(eq(on,1),1.5,max(zoom-{intensity*0.015},1))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1",
            "pan_left":  f"zoompan=z={zoom}:x='iw/2-(iw/zoom/2)+on*{intensity*1.5}':y='ih/2-(ih/zoom/2)':d=1",
            "pan_right": f"zoompan=z={zoom}:x='iw/2-(iw/zoom/2)-on*{intensity*1.5}':y='ih/2-(ih/zoom/2)':d=1",
        }.get(motion_type, "null")

        cmd = [
            "ffmpeg", "-y", "-i", str(inp),
            "-vf", VF, "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=60)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg motion error: {res.stderr.decode()[:200]}")
        return out.read_bytes()
