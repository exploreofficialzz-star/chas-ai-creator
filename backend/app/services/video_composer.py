"""
Video composer service using FFmpeg.
FILE: app/services/video_composer.py

FIXES:
1. CRITICAL — subprocess.create_subprocess_exec doesn't exist.
   It's asyncio.create_subprocess_exec. All FFmpeg calls crashed.

2. compose_video() missing audio_mode param passed by video_generation.py.

3. Caption filter hardcoded "Sample Caption" — now uses actual scene captions.

4. _download_scenes() now downloads directly via httpx instead of
   StorageService.download_file() which may not exist.

5. get_video_info() was sync — replaced with async.

6. FFmpeg not on PATH — added auto-detection of common paths.

7. Images need -loop 1 + -t duration per input (not concat demuxer).

8. Audio filter_complex had wrong input indices.

9. NEW — Crossfade transitions between scenes using xfade filter.
   Each scene transition gets a smooth 0.5s crossfade making the video
   look much more professional instead of hard cuts.

10. NEW — Scenes with Ken Burns clips (from video_generation.py)
    are now properly chained through xfade for smooth playback.
"""

import asyncio
import json
import os
import random
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

VIDEO_RESOLUTIONS = {
    "9:16":  {"width": 720,  "height": 1280},
    "16:9":  {"width": 1280, "height": 720},
    "1:1":   {"width": 720,  "height": 720},
}

# xfade transition effects — randomly applied between scenes
_XFADE_EFFECTS = [
    "fade", "fadeblack", "fadegrays",
    "smoothleft", "smoothright",
    "slideleft", "slideright",
    "dissolve",
]

TRANSITION_DURATION = 0.5   # seconds of crossfade between scenes


def _find_ffmpeg() -> str:
    for path in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if shutil.which(path):
            return path
    return "ffmpeg"


def _find_ffprobe() -> str:
    for path in ["ffprobe", "/usr/bin/ffprobe", "/usr/local/bin/ffprobe"]:
        if shutil.which(path):
            return path
    return "ffprobe"


class VideoComposerService:

    def __init__(self):
        self.ffmpeg   = _find_ffmpeg()
        self.ffprobe  = _find_ffprobe()
        self.storage  = StorageService()
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
        audio_mode: str = "silent",   # FIX 2
    ) -> str:
        if not output_filename:
            output_filename = f"videos/{uuid.uuid4()}.mp4"

        work_dir = tempfile.mkdtemp(dir=self.temp_dir)

        try:
            resolution  = VIDEO_RESOLUTIONS.get(
                aspect_ratio, VIDEO_RESOLUTIONS["9:16"]
            )
            scene_files = await self._download_scenes(scenes, work_dir)

            if not scene_files:
                raise Exception("No scene files downloaded")

            output_path = os.path.join(work_dir, "output.mp4")

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
        """FIX 5 — async version."""
        cmd = [
            self.ffprobe, "-v", "error",
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
                "duration": float(
                    info.get("format", {}).get("duration", 0)
                ),
                "width":   info.get("streams", [{}])[0].get("width"),
                "height":  info.get("streams", [{}])[0].get("height"),
                "size":    int(info.get("format", {}).get("size", 0)),
                "bitrate": int(
                    info.get("format", {}).get("bit_rate", 0)
                ),
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
        width  = resolution["width"]
        height = resolution["height"]

        # Download audio tracks
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
                work_dir=work_dir,
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
        FIX 7 + FIX 9 — Build individual clips then join with xfade transitions.
        Each image gets Ken Burns motion + caption, then smooth crossfade between.
        """
        clip_paths = []

        for i, (img, scene) in enumerate(zip(image_files, scenes)):
            dur     = float(scene.get("duration", 3.0))
            caption = scene.get("caption", "")
            clip_out = os.path.join(work_dir, f"clip_{i:03d}.mp4")

            # Ken Burns effect — each scene gets a different random motion
            motion_presets = [
                f"zoompan=z='min(zoom+0.0008,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
                f"zoompan=z='if(eq(on,1),1.15,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
                f"zoompan=z=1.08:x='iw/2-(iw/zoom/2)+on*0.35':y='ih/2-(ih/zoom/2)'",
                f"zoompan=z=1.08:x='iw/2-(iw/zoom/2)-on*0.35':y='ih/2-(ih/zoom/2)'",
                f"zoompan=z='min(zoom+0.0006,1.10)':x='iw/2-(iw/zoom/2)':y='ih-(ih/zoom)-on*0.15'",
                f"zoompan=z=1.08:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+on*0.25'",
            ]
            motion = motion_presets[i % len(motion_presets)]
            fps    = 30
            frames = int(dur * fps)

            vf_parts = [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                "setsar=1",
                f"{motion}:d={frames}:s={width}x{height}",
                f"scale={width}:{height}",
            ]

            # Add caption if enabled
            if captions_config and captions_config.get("enabled") and caption:
                caption_filter = self._build_caption_filter(
                    caption, width, height, captions_config
                )
                if caption_filter:
                    vf_parts.append(caption_filter)

            clip_cmd = [
                self.ffmpeg, "-y",
                "-loop", "1",
                "-i", img,
                "-t", str(dur),
                "-vf", ",".join(vf_parts),
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-an",
                clip_out,
            ]
            await self._run_ffmpeg(clip_cmd)
            clip_paths.append(clip_out)

        # Join clips with crossfade transitions
        # FIX 9 — smooth xfade between every pair of scenes
        joined_path = os.path.join(work_dir, "joined.mp4")
        await self._join_with_xfade(clip_paths, scenes, joined_path, width, height)

        # Add audio
        await self._add_audio(
            video_path=joined_path,
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
        work_dir: str,
    ) -> None:
        """
        FIX 9 — Compose from video clips (from VideoGenerationService)
        with xfade crossfade transitions between scenes.
        """
        # First normalise all clips to same resolution
        normalised = []
        for i, clip in enumerate(clip_files):
            norm_out = os.path.join(work_dir, f"norm_{i:03d}.mp4")
            scene    = scenes[i] if i < len(scenes) else {}
            caption  = scene.get("caption", "")

            vf_parts = [
                f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                "setsar=1",
            ]

            if captions_config and captions_config.get("enabled") and caption:
                caption_filter = self._build_caption_filter(
                    caption, width, height, captions_config
                )
                if caption_filter:
                    vf_parts.append(caption_filter)

            norm_cmd = [
                self.ffmpeg, "-y",
                "-i", clip,
                "-vf", ",".join(vf_parts),
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                "-an",
                norm_out,
            ]
            try:
                await self._run_ffmpeg(norm_cmd)
                normalised.append(norm_out)
            except Exception as e:
                logger.warning(f"Could not normalise clip {i}: {e}")
                normalised.append(clip)

        # Join with xfade
        joined_path = os.path.join(work_dir, "joined.mp4")
        await self._join_with_xfade(
            normalised, scenes, joined_path, width, height
        )

        # Add audio
        await self._add_audio(
            video_path=joined_path,
            output_path=output_path,
            narration_path=narration_path,
            music_path=music_path,
        )

    # ─── XFADE TRANSITIONS ────────────────────────────────────────────────────

    async def _join_with_xfade(
        self,
        clip_paths: List[str],
        scenes: List[Dict[str, Any]],
        output_path: str,
        width: int,
        height: int,
    ) -> None:
        """
        FIX 9 — Join clips with smooth xfade crossfade transitions.
        Falls back to simple concat if xfade filter fails.
        """
        if len(clip_paths) == 1:
            shutil.copy2(clip_paths[0], output_path)
            return

        try:
            await self._xfade_chain(
                clip_paths, scenes, output_path, width, height
            )
        except Exception as e:
            logger.warning(
                f"xfade failed ({e}), falling back to simple concat"
            )
            await self._simple_concat(clip_paths, output_path)

    async def _xfade_chain(
        self,
        clip_paths: List[str],
        scenes: List[Dict[str, Any]],
        output_path: str,
        width: int,
        height: int,
    ) -> None:
        """
        Build FFmpeg xfade filter_complex chain for smooth transitions.
        Formula: each pair (A, B) uses offset = A_duration - TRANSITION_DURATION
        """
        # Get durations for each clip
        durations = []
        for i, clip in enumerate(clip_paths):
            d = float(
                scenes[i].get("duration", 3.0) if i < len(scenes) else 3.0
            )
            durations.append(d)

        n = len(clip_paths)
        td = TRANSITION_DURATION

        # Build -i inputs
        cmd = [self.ffmpeg, "-y"]
        for clip in clip_paths:
            cmd.extend(["-i", clip])

        # Build filter_complex
        # Each xfade: offset = cumulative_duration_so_far - td
        filter_parts = []
        cumulative   = 0.0
        prev_label   = "[0:v]"

        for i in range(1, n):
            cumulative += durations[i - 1]
            offset = max(0.0, cumulative - td)
            effect = random.choice(_XFADE_EFFECTS)
            next_label = f"[v{i}]" if i < n - 1 else "[vout]"
            filter_parts.append(
                f"{prev_label}[{i}:v]xfade=transition={effect}:"
                f"duration={td}:offset={offset:.3f}{next_label}"
            )
            prev_label = next_label
            cumulative -= td   # account for overlap

        filter_complex = ";".join(filter_parts)

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-an",
            output_path,
        ])
        await self._run_ffmpeg(cmd)

    async def _simple_concat(
        self, clip_paths: List[str], output_path: str
    ) -> None:
        """Fallback: simple concat with no transitions."""
        work_dir    = os.path.dirname(output_path)
        concat_file = os.path.join(work_dir, "fallback_concat.txt")
        with open(concat_file, "w") as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ]
        await self._run_ffmpeg(cmd)

    # ─── AUDIO MIXING ─────────────────────────────────────────────────────────

    async def _add_audio(
        self,
        video_path: str,
        output_path: str,
        narration_path: Optional[str],
        music_path: Optional[str],
    ) -> None:
        """FIX 8 — Correct audio input index tracking."""
        if not narration_path and not music_path:
            shutil.copy2(video_path, output_path)
            return

        cmd         = [self.ffmpeg, "-y", "-i", video_path]
        audio_index = 1

        if narration_path:
            cmd.extend(["-i", narration_path])
            na_idx = audio_index
            audio_index += 1
        else:
            na_idx = None

        if music_path:
            cmd.extend(["-i", music_path])
            bg_idx = audio_index
        else:
            bg_idx = None

        if na_idx is not None and bg_idx is not None:
            cmd.extend([
                "-filter_complex",
                f"[{na_idx}:a]volume=1.0[na];"
                f"[{bg_idx}:a]volume=0.22[bg];"
                f"[na][bg]amix=inputs=2:duration=first[aout]",
                "-map", "0:v",
                "-map", "[aout]",
            ])
        elif na_idx is not None:
            cmd.extend(["-map", "0:v", "-map", f"{na_idx}:a"])
        elif bg_idx is not None:
            cmd.extend(["-map", "0:v", "-map", f"{bg_idx}:a"])

        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ])
        await self._run_ffmpeg(cmd)

    # ─── CAPTION FILTER ───────────────────────────────────────────────────────

    def _build_caption_filter(
        self,
        caption: str,
        width: int,
        height: int,
        config: Dict,
    ) -> str:
        """FIX 3 — Build drawtext filter with actual scene caption."""
        style    = config.get("style", "modern")
        color    = config.get("color", "white")
        fontsize = int(height * 0.055)
        y_pos    = int(height * 0.82)

        import re
        # Remove emojis (FFmpeg drawtext can't render them)
        clean = re.sub(
            r'[\U00010000-\U0010ffff]', '', caption, flags=re.UNICODE
        ).strip()
        if not clean:
            return ""

        # Escape FFmpeg special characters
        clean = (
            clean
            .replace("\\", "\\\\")
            .replace("'", "\u2019")    # replace apostrophe with right quote
            .replace(":", "\\:")
            .replace("[", "\\[")
            .replace("]", "\\]")
        )

        box = "1" if style in ("modern", "bold") else "0"
        return (
            f"drawtext=text='{clean}':"
            f"fontsize={fontsize}:"
            f"fontcolor={color}:"
            f"x=(w-text_w)/2:"
            f"y={y_pos}:"
            f"borderw=3:"
            f"bordercolor=black@0.6:"
            f"box={box}:"
            f"boxcolor=black@0.35:"
            f"boxborderw=8"
        )

    # ─── DOWNLOAD / UTILS ─────────────────────────────────────────────────────

    async def _download_scenes(
        self, scenes: List[Dict], work_dir: str
    ) -> List[str]:
        """FIX 4 — Download directly via httpx."""
        files = []
        for i, scene in enumerate(scenes):
            url = scene.get("video_clip_url") or scene.get("image_url")
            if not url:
                continue
            try:
                ext = ".mp4" if (
                    "clips" in url or url.endswith(".mp4")
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
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=60.0
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content

    def _create_concat_file(
        self, files: List[str], work_dir: str
    ) -> str:
        concat_path = os.path.join(work_dir, "concat.txt")
        with open(concat_path, "w") as f:
            for fp in files:
                escaped = fp.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
        return concat_path

    # FIX 1 — asyncio.create_subprocess_exec
    async def _run_ffmpeg(self, cmd: List[str]) -> None:
        logger.info(f"FFmpeg: {' '.join(cmd[:8])}...")
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
