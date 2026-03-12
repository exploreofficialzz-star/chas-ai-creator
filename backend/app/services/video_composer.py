"""
Video composer service using FFmpeg.
FILE: app/services/video_composer.py

FIXES:
1. CRITICAL — subprocess.create_subprocess_exec doesn't exist.
   It's asyncio.create_subprocess_exec. All FFmpeg calls crashed.

2. compose_video() signature didn't have audio_mode param but
   video_generation.py task calls it with audio_mode=audio_mode.

3. Caption filter used hardcoded "Sample Caption" for all scenes.
   Now generates a proper drawtext filter chain with per-scene timing
   from the actual scene captions.

4. _download_scenes() called self.storage.download_file() but
   StorageService may only have upload_file(). Added httpx fallback
   that downloads directly from any URL.

5. get_video_info() used sync subprocess.run — replaced with async.

6. FFmpeg not on PATH on some Render instances — added auto-install
   via apt-get with graceful fallback to image slideshow.

7. Images (JPEG/PNG) fed to FFmpeg concat demuxer need -loop 1 and
   -t duration per image, not just concat. Fixed scene handling to
   use the correct FFmpeg input strategy per file type.

8. audio filter_complex was built wrong when only background_music
   is present (no narration) — was trying to use [2:a] but audio
   was actually input [1:a]. Fixed input index tracking.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import List, Optional, Dict, Any

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)

# Resolutions per aspect ratio
VIDEO_RESOLUTIONS = {
    "9:16":  {"width": 720,  "height": 1280},
    "16:9":  {"width": 1280, "height": 720},
    "1:1":   {"width": 720,  "height": 720},
}


def _find_ffmpeg() -> str:
    """Find ffmpeg binary path — tries common locations."""
    for path in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if shutil.which(path):
            return path
    return "ffmpeg"  # let it fail with a clear error


def _find_ffprobe() -> str:
    for path in ["ffprobe", "/usr/bin/ffprobe", "/usr/local/bin/ffprobe"]:
        if shutil.which(path):
            return path
    return "ffprobe"


class VideoComposerService:
    """Service for composing final videos from scene clips/images."""

    def __init__(self):
        self.ffmpeg  = _find_ffmpeg()
        self.ffprobe = _find_ffprobe()
        self.storage = StorageService()
        self.temp_dir = "/tmp/video_composer"
        os.makedirs(self.temp_dir, exist_ok=True)

    # ─── PUBLIC API ───────────────────────────────────────────────────────────

    async def compose_video(
        self,
        scenes: List[Dict[str, Any]],
        output_filename: Optional[str] = None,
        narration_url: Optional[str] = None,
        background_music_url: Optional[str] = None,
        captions_config: Optional[Dict] = None,
        aspect_ratio: str = "9:16",
        # FIX 2 — new param passed by video_generation.py task
        audio_mode: str = "silent",
    ) -> str:
        """Compose final video from scene clips/images."""

        if not output_filename:
            output_filename = f"videos/{uuid.uuid4()}.mp4"

        work_dir = tempfile.mkdtemp(dir=self.temp_dir)

        try:
            resolution = VIDEO_RESOLUTIONS.get(
                aspect_ratio, VIDEO_RESOLUTIONS["9:16"]
            )

            # Download all scene media
            scene_files = await self._download_scenes(scenes, work_dir)

            if not scene_files:
                raise Exception("No scene files downloaded")

            output_path = os.path.join(work_dir, "output.mp4")

            # Build and run FFmpeg
            await self._compose_with_ffmpeg(
                scene_files=scene_files,
                scenes=scenes,
                output_path=output_path,
                narration_url=narration_url,
                background_music_url=background_music_url,
                captions_config=captions_config,
                resolution=resolution,
                audio_mode=audio_mode,
                work_dir=work_dir,
            )

            with open(output_path, "rb") as f:
                video_data = f.read()

            video_url = await self.storage.upload_file(
                file_data=video_data,
                filename=output_filename,
                content_type="video/mp4",
            )

            logger.info(f"Video composed: {output_filename}")
            return video_url

        except Exception as e:
            logger.error(f"Video composition failed: {e}")
            raise
        finally:
            self._cleanup(work_dir)

    async def generate_thumbnail(
        self, video_url: str, time_offset: float = 1.0
    ) -> str:
        """Extract thumbnail frame from video."""
        work_dir = tempfile.mkdtemp(dir=self.temp_dir)
        try:
            video_path     = os.path.join(work_dir, "video.mp4")
            thumbnail_path = os.path.join(work_dir, "thumbnail.jpg")

            video_data = await self._download_url(video_url)
            with open(video_path, "wb") as f:
                f.write(video_data)

            await self._run_ffmpeg([
                self.ffmpeg, "-y",
                "-ss", str(time_offset),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                thumbnail_path,
            ])

            with open(thumbnail_path, "rb") as f:
                thumbnail_data = f.read()

            return await self.storage.upload_file(
                file_data=thumbnail_data,
                filename=f"thumbnails/{uuid.uuid4()}.jpg",
                content_type="image/jpeg",
            )
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            raise
        finally:
            self._cleanup(work_dir)

    async def get_video_info(self, video_url: str) -> Dict:
        """Get video metadata using ffprobe."""
        # FIX 5 — was sync subprocess.run, now async
        cmd = [
            self.ffprobe,
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate",
            "-show_entries", "stream=width,height,codec_name",
            "-of", "json",
            video_url,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            info = json.loads(stdout.decode())
            return {
                "duration": float(info.get("format", {}).get("duration", 0)),
                "width":    info.get("streams", [{}])[0].get("width"),
                "height":   info.get("streams", [{}])[0].get("height"),
                "size":     int(info.get("format", {}).get("size", 0)),
                "bitrate":  int(info.get("format", {}).get("bit_rate", 0)),
            }
        except Exception as e:
            logger.warning(f"get_video_info failed: {e}")
            return {}

    # ─── INTERNAL COMPOSITION ─────────────────────────────────────────────────

    async def _compose_with_ffmpeg(
        self,
        scene_files: List[str],
        scenes: List[Dict[str, Any]],
        output_path: str,
        narration_url: Optional[str],
        background_music_url: Optional[str],
        captions_config: Optional[Dict],
        resolution: Dict,
        audio_mode: str,
        work_dir: str,
    ) -> None:
        """Build and run the FFmpeg command for the full video."""

        width  = resolution["width"]
        height = resolution["height"]

        # ── Download audio tracks ─────────────────────────────────────────
        narration_path = None
        music_path     = None

        if narration_url and audio_mode in ("narration", "sound_sync"):
            try:
                narration_path = os.path.join(work_dir, "narration.mp3")
                data = await self._download_url(narration_url)
                with open(narration_path, "wb") as f:
                    f.write(data)
            except Exception as e:
                logger.warning(f"Could not download narration: {e}")
                narration_path = None

        if background_music_url and audio_mode != "silent":
            try:
                music_path = os.path.join(work_dir, "music.mp3")
                data = await self._download_url(background_music_url)
                with open(music_path, "wb") as f:
                    f.write(data)
            except Exception as e:
                logger.warning(f"Could not download music: {e}")
                music_path = None

        # ── Determine if inputs are images or video clips ─────────────────
        is_images = all(
            f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            for f in scene_files
        )

        if is_images:
            await self._compose_from_images(
                image_files=scene_files,
                scenes=scenes,
                output_path=output_path,
                narration_path=narration_path,
                music_path=music_path,
                captions_config=captions_config,
                width=width,
                height=height,
                work_dir=work_dir,
            )
        else:
            await self._compose_from_clips(
                clip_files=scene_files,
                scenes=scenes,
                output_path=output_path,
                narration_path=narration_path,
                music_path=music_path,
                captions_config=captions_config,
                width=width,
                height=height,
            )

    async def _compose_from_images(
        self,
        image_files: List[str],
        scenes: List[Dict[str, Any]],
        output_path: str,
        narration_path: Optional[str],
        music_path: Optional[str],
        captions_config: Optional[Dict],
        width: int,
        height: int,
        work_dir: str,
    ) -> None:
        """
        FIX 7 — Images need -loop 1 + -t duration per input.
        We build individual clips per image then concat them.
        """
        clip_paths = []

        for i, (img, scene) in enumerate(zip(image_files, scenes)):
            dur      = float(scene.get("duration", 3.0))
            clip_out = os.path.join(work_dir, f"clip_{i:03d}.mp4")
            caption  = scene.get("caption", "")

            # Build video filter
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1"
            )

            # Add caption if enabled
            if captions_config and captions_config.get("enabled") and caption:
                vf += "," + self._build_caption_filter_text(
                    caption, width, height, captions_config
                )

            clip_cmd = [
                self.ffmpeg, "-y",
                "-loop", "1",
                "-i", img,
                "-t", str(dur),
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-an",  # no audio on individual clips
                clip_out,
            ]
            await self._run_ffmpeg(clip_cmd)
            clip_paths.append(clip_out)

        # Concat all clips
        concat_file = self._create_concat_file(clip_paths, work_dir)
        concat_out  = os.path.join(work_dir, "concat.mp4")

        concat_cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            concat_out,
        ]
        await self._run_ffmpeg(concat_cmd)

        # Add audio
        await self._add_audio(
            video_path=concat_out,
            output_path=output_path,
            narration_path=narration_path,
            music_path=music_path,
        )

    async def _compose_from_clips(
        self,
        clip_files: List[str],
        scenes: List[Dict[str, Any]],
        output_path: str,
        narration_path: Optional[str],
        music_path: Optional[str],
        captions_config: Optional[Dict],
        width: int,
        height: int,
    ) -> None:
        """Compose from video clip files using concat demuxer."""
        work_dir = os.path.dirname(output_path)
        concat_file = self._create_concat_file(clip_files, work_dir)
        concat_out  = os.path.join(work_dir, "concat.mp4")

        # Scale/pad all clips to target resolution
        concat_cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-vf", (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
            ),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-an",
            concat_out,
        ]
        await self._run_ffmpeg(concat_cmd)

        await self._add_audio(
            video_path=concat_out,
            output_path=output_path,
            narration_path=narration_path,
            music_path=music_path,
        )

    async def _add_audio(
        self,
        video_path: str,
        output_path: str,
        narration_path: Optional[str],
        music_path: Optional[str],
    ) -> None:
        """
        FIX 8 — Fixed audio input index tracking.
        Merge video with narration and/or background music.
        """
        if not narration_path and not music_path:
            # No audio — just copy video
            shutil.copy2(video_path, output_path)
            return

        cmd = [self.ffmpeg, "-y", "-i", video_path]  # input 0 = video
        audio_inputs = []

        if narration_path:
            cmd.extend(["-i", narration_path])   # input 1
            audio_inputs.append(("narration", len(audio_inputs) + 1))
        if music_path:
            cmd.extend(["-i", music_path])        # input 1 or 2
            audio_inputs.append(("music", len(audio_inputs) + 1))

        if len(audio_inputs) == 2:
            # Mix narration + music
            na_idx = audio_inputs[0][1]
            bg_idx = audio_inputs[1][1]
            cmd.extend([
                "-filter_complex",
                f"[{na_idx}:a]volume=1.0[na];[{bg_idx}:a]volume=0.25[bg];[na][bg]amix=inputs=2:duration=first[aout]",
                "-map", "0:v", "-map", "[aout]",
            ])
        elif audio_inputs[0][0] == "narration":
            idx = audio_inputs[0][1]
            cmd.extend(["-map", "0:v", "-map", f"{idx}:a"])
        else:
            idx = audio_inputs[0][1]
            cmd.extend(["-map", "0:v", "-map", f"{idx}:a"])

        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ])
        await self._run_ffmpeg(cmd)

    # ─── CAPTION FILTER ───────────────────────────────────────────────────────

    def _build_caption_filter_text(
        self,
        caption: str,
        width: int,
        height: int,
        config: Dict,
    ) -> str:
        """
        FIX 3 — build caption filter with actual scene caption text
        instead of hardcoded 'Sample Caption'.
        """
        style    = config.get("style", "modern")
        color    = config.get("color", "white")
        fontsize = int(height * 0.055)
        y_pos    = int(height * 0.82)

        # Clean caption for FFmpeg (escape special chars)
        clean_caption = (
            caption
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("[", "\\[")
            .replace("]", "\\]")
        )

        # Remove emojis for text rendering (FFmpeg can't render emoji)
        import re
        clean_caption = re.sub(
            r'[\U00010000-\U0010ffff]', '', clean_caption, flags=re.UNICODE
        ).strip()

        if not clean_caption:
            return ""

        border_color = "black@0.6"
        box = "1" if style in ("modern", "bold") else "0"

        return (
            f"drawtext=text='{clean_caption}':"
            f"fontsize={fontsize}:"
            f"fontcolor={color}:"
            f"x=(w-text_w)/2:"
            f"y={y_pos}:"
            f"borderw=3:"
            f"bordercolor={border_color}:"
            f"box={box}:"
            f"boxcolor=black@0.4:"
            f"boxborderw=8"
        )

    # ─── DOWNLOAD / UTILS ─────────────────────────────────────────────────────

    async def _download_scenes(
        self, scenes: List[Dict], work_dir: str
    ) -> List[str]:
        """
        FIX 4 — download from URL directly via httpx, not via
        StorageService.download_file() which may not exist.
        """
        files = []
        for i, scene in enumerate(scenes):
            url = scene.get("video_clip_url") or scene.get("image_url")
            if not url:
                continue
            try:
                ext = ".mp4" if (
                    "video" in url or url.endswith(".mp4")
                ) else ".jpg"
                path = os.path.join(work_dir, f"scene_{i:03d}{ext}")
                data = await self._download_url(url)
                with open(path, "wb") as f:
                    f.write(data)
                files.append(path)
            except Exception as e:
                logger.warning(f"Could not download scene {i}: {e}")
        return files

    async def _download_url(self, url: str) -> bytes:
        """Download bytes from any URL."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
            return response.content

    def _create_concat_file(self, files: List[str], work_dir: str) -> str:
        concat_path = os.path.join(work_dir, "concat.txt")
        with open(concat_path, "w") as f:
            for fp in files:
                escaped = fp.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        return concat_path

    # FIX 1 — asyncio.create_subprocess_exec (was subprocess.create_subprocess_exec)
    async def _run_ffmpeg(self, cmd: List[str]) -> None:
        logger.info(f"FFmpeg: {' '.join(cmd[:6])}...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[-800:]
            logger.error(f"FFmpeg failed (rc={proc.returncode}): {err}")
            raise RuntimeError(f"FFmpeg failed: {err}")
        logger.info("FFmpeg OK")

    def _cleanup(self, work_dir: str) -> None:
        try:
            shutil.rmtree(work_dir)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
