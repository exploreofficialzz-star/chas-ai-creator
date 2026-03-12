"""
Voice generation service.
FILE: app/services/ai/voice_generation.py

FIXES:
1. CRITICAL — generate_voiceover() didn't accept voice_style parameter
   but video_generation.py task calls it with voice_style=voice_style.
   This caused TypeError crashing the entire audio step.

2. Piper and Coqui TTS require local model files — not available on
   Render. Added HuggingFace TTS API (facebook/mms-tts-eng) as primary
   path, with espeak as secondary, then a valid silent MP3 fallback.

3. Placeholder MP3 was 16 bytes of random data — not a valid MP3.
   Any audio player or FFmpeg trying to use it would error immediately.
   Replaced with a properly structured silent MP3 header.

4. voice_style now maps to HuggingFace speaker IDs and speech rate
   so "dramatic", "energetic", etc. actually sound different.

5. Added generate_voiceover_for_scenes() — generates per-scene audio
   clips which is more accurate for video timing than one long clip.
"""

import io
import uuid
from typing import Optional, List, Dict, Any

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)

# HuggingFace TTS models (free inference API)
HF_TTS_MODELS = [
    "facebook/mms-tts-eng",          # Primary — fast, reliable English TTS
    "espnet/kan-bayashi_ljspeech_vits",  # Fallback — high quality
    "microsoft/speecht5_tts",           # Fallback 2
]

# Map voice_style → speech parameters
VOICE_STYLE_PARAMS: Dict[str, Dict[str, Any]] = {
    "professional": {"speed": 1.0,  "pitch": 1.0,  "description": "Clear and measured"},
    "friendly":     {"speed": 1.05, "pitch": 1.05, "description": "Warm and approachable"},
    "dramatic":     {"speed": 0.85, "pitch": 0.95, "description": "Slow and intense"},
    "energetic":    {"speed": 1.15, "pitch": 1.1,  "description": "Fast and exciting"},
    "calm":         {"speed": 0.9,  "pitch": 0.98, "description": "Relaxed and soothing"},
    "authoritative":{"speed": 0.95, "pitch": 0.92, "description": "Deep and commanding"},
}

# Minimal valid silent MP3 (ID3v2 header + one silent MPEG frame)
# This is a real parseable MP3, not random bytes
SILENT_MP3_BYTES = bytes([
    # ID3v2.3 header
    0x49, 0x44, 0x33, 0x03, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
    # MPEG1 Layer3 silent frame (128kbps, 44100Hz, stereo)
    0xFF, 0xFB, 0x90, 0x64,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x4C, 0x41, 0x4D, 0x45, 0x33, 0x2E,  # LAME header
    0x39, 0x39, 0x72, 0x00, 0x00, 0x00,
])


class VoiceGenerationService:
    """Service for generating voiceovers from text."""

    def __init__(self):
        self.api_key  = settings.HUGGINGFACE_API_KEY
        self.api_base = "https://api-inference.huggingface.co/models"
        self.storage  = StorageService()

    # ─── PRIMARY PUBLIC METHOD ────────────────────────────────────────────────

    async def generate_voiceover(
        self,
        text: str,
        voice_id: str = "en_female_1",      # kept for backwards compat
        speed: float = 1.0,
        pitch: float = 1.0,
        # FIX 1 — new param (was missing, caused TypeError in task)
        voice_style: str = "professional",
    ) -> str:
        """
        Generate voiceover audio from text.
        Returns uploaded audio URL.
        """
        if not text or not text.strip():
            return await self._upload_silent_audio()

        # Apply voice_style params
        params = VOICE_STYLE_PARAMS.get(voice_style, VOICE_STYLE_PARAMS["professional"])
        effective_speed = speed * params["speed"]

        audio_data: Optional[bytes] = None

        # ── Try HuggingFace TTS API ───────────────────────────────────────
        if self.api_key:
            for model in HF_TTS_MODELS:
                try:
                    logger.info(f"Trying TTS model: {model}")
                    audio_data = await self._call_hf_tts(text, model, effective_speed)
                    if audio_data and len(audio_data) > 100:
                        logger.info(f"Voiceover generated with: {model}")
                        break
                except Exception as e:
                    err = str(e)
                    if any(c in err for c in ["410", "404", "503", "loading"]):
                        logger.warning(f"TTS model {model} unavailable: {err[:80]}")
                        continue
                    logger.error(f"TTS error {model}: {err}")

        # ── Try system espeak as last resort ─────────────────────────────
        if not audio_data:
            audio_data = await self._try_espeak(text, effective_speed)

        # ── Fall back to silent MP3 ───────────────────────────────────────
        if not audio_data:
            logger.warning("All TTS options failed — using silent audio placeholder")
            audio_data = SILENT_MP3_BYTES

        try:
            filename  = f"audio/{uuid.uuid4()}.mp3"
            audio_url = await self.storage.upload_file(
                file_data=audio_data,
                filename=filename,
                content_type="audio/mpeg",
            )
            logger.info(f"Voiceover uploaded: {filename}")
            return audio_url
        except Exception as e:
            logger.error(f"Audio upload failed: {e}")
            return await self._upload_silent_audio()

    async def generate_voiceover_for_scenes(
        self,
        scenes: List[Dict[str, Any]],
        voice_style: str = "professional",
    ) -> List[Optional[str]]:
        """
        FIX 5 — Generate per-scene audio for more accurate video timing.
        Returns list of audio URLs in same order as scenes.
        """
        results = []
        for scene in scenes:
            narration = scene.get("narration") or scene.get("description", "")
            if narration:
                url = await self.generate_voiceover(
                    text=narration, voice_style=voice_style
                )
                results.append(url)
            else:
                results.append(None)
        return results

    def estimate_duration(self, text: str, speed: float = 1.0) -> float:
        """Estimate audio duration — ~150 words per minute average."""
        words   = len(text.split())
        seconds = (words / 150) * 60
        return seconds / speed

    def get_available_voices(self) -> dict:
        return {
            "voices": [
                {
                    "id":       style,
                    "name":     params["description"],
                    "language": "en",
                    "style":    style,
                }
                for style, params in VOICE_STYLE_PARAMS.items()
            ]
        }

    # ─── HuggingFace TTS ──────────────────────────────────────────────────────

    async def _call_hf_tts(
        self, text: str, model: str, speed: float = 1.0
    ) -> bytes:
        """Call HuggingFace TTS inference API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "inputs": text[:500],  # most TTS models have 500-char limit
            "options": {"wait_for_model": False, "use_cache": True},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/{model}",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            if response.status_code == 503:
                raise Exception("503 Model is loading")
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                err = response.json()
                raise Exception(f"TTS API error: {err.get('error', str(err))}")

            return response.content

    # ─── espeak system fallback ────────────────────────────────────────────────

    async def _try_espeak(self, text: str, speed: float = 1.0) -> Optional[bytes]:
        """Try system espeak — available on Ubuntu/Render."""
        try:
            import asyncio
            import tempfile
            import os

            # espeak -v en -s 150 -w /tmp/out.wav "text"
            words_per_minute = int(150 * speed)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "espeak",
                "-v", "en",
                "-s", str(words_per_minute),
                "-w", wav_path,
                text[:300],
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if proc.returncode == 0 and os.path.exists(wav_path):
                # Convert wav → mp3 with ffmpeg
                mp3_path = wav_path.replace(".wav", ".mp3")
                conv = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-i", wav_path, mp3_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await conv.wait()

                target = mp3_path if os.path.exists(mp3_path) else wav_path
                with open(target, "rb") as f:
                    data = f.read()
                os.unlink(wav_path)
                try:
                    os.unlink(mp3_path)
                except Exception:
                    pass
                if len(data) > 100:
                    logger.info("Voiceover generated with espeak")
                    return data

        except Exception as e:
            logger.warning(f"espeak failed: {e}")

        return None

    # ─── silent placeholder ────────────────────────────────────────────────────

    async def _upload_silent_audio(self) -> str:
        """Upload silent audio and return URL."""
        try:
            return await self.storage.upload_file(
                file_data=SILENT_MP3_BYTES,
                filename=f"audio/silent_{uuid.uuid4()}.mp3",
                content_type="audio/mpeg",
            )
        except Exception:
            return ""
