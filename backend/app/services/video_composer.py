"""Video composer service using FFmpeg."""

import os
import subprocess
import tempfile
import uuid
from typing import List, Optional, Dict, Any

from app.config import settings
from app.core.logging import get_logger
from app.services.storage import StorageService

logger = get_logger(__name__)


class VideoComposerService:
    """Service for composing final videos from clips."""
    
    def __init__(self):
        self.ffmpeg_path = settings.FFMPEG_PATH
        self.storage = StorageService()
        self.temp_dir = "/tmp/video_composer"
        
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def compose_video(
        self,
        scenes: List[Dict[str, Any]],
        output_filename: Optional[str] = None,
        narration_url: Optional[str] = None,
        background_music_url: Optional[str] = None,
        captions_config: Optional[Dict] = None,
        aspect_ratio: str = "9:16",
        target_resolution: Optional[Dict] = None,
    ) -> str:
        """Compose final video from scenes."""
        
        if not output_filename:
            output_filename = f"videos/{uuid.uuid4()}.mp4"
        
        work_dir = tempfile.mkdtemp(dir=self.temp_dir)
        
        try:
            # Download all assets
            scene_files = await self._download_scenes(scenes, work_dir)
            
            # Create concat file
            concat_file = self._create_concat_file(scene_files, work_dir)
            
            # Get resolution
            if not target_resolution:
                target_resolution = settings.VIDEO_RESOLUTIONS.get(
                    aspect_ratio, {"width": 1080, "height": 1920}
                )
            
            # Build FFmpeg command
            output_path = os.path.join(work_dir, "output.mp4")
            
            cmd = self._build_ffmpeg_command(
                concat_file=concat_file,
                output_path=output_path,
                narration_url=narration_url,
                background_music_url=background_music_url,
                captions_config=captions_config,
                resolution=target_resolution,
            )
            
            # Execute FFmpeg
            await self._run_ffmpeg(cmd)
            
            # Read output file
            with open(output_path, "rb") as f:
                video_data = f.read()
            
            # Upload to storage
            video_url = await self.storage.upload_file(
                file_data=video_data,
                filename=output_filename,
                content_type="video/mp4",
            )
            
            logger.info("Video composed successfully", filename=output_filename)
            return video_url
            
        except Exception as e:
            logger.error("Video composition failed", error=str(e))
            raise
        
        finally:
            # Cleanup
            self._cleanup(work_dir)
    
    async def _download_scenes(
        self,
        scenes: List[Dict],
        work_dir: str,
    ) -> List[str]:
        """Download scene video clips."""
        
        scene_files = []
        
        for i, scene in enumerate(scenes):
            video_url = scene.get("video_clip_url") or scene.get("image_url")
            
            if not video_url:
                continue
            
            # Download
            ext = ".mp4" if "video" in video_url else ".jpg"
            scene_path = os.path.join(work_dir, f"scene_{i:03d}{ext}")
            
            data = await self.storage.download_file(video_url)
            
            with open(scene_path, "wb") as f:
                f.write(data)
            
            scene_files.append(scene_path)
        
        return scene_files
    
    def _create_concat_file(
        self,
        scene_files: List[str],
        work_dir: str,
    ) -> str:
        """Create FFmpeg concat demuxer file."""
        
        concat_path = os.path.join(work_dir, "concat.txt")
        
        with open(concat_path, "w") as f:
            for scene_file in scene_files:
                # Escape single quotes in path
                escaped_path = scene_file.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        return concat_path
    
    def _build_ffmpeg_command(
        self,
        concat_file: str,
        output_path: str,
        narration_url: Optional[str],
        background_music_url: Optional[str],
        captions_config: Optional[Dict],
        resolution: Dict,
    ) -> List[str]:
        """Build FFmpeg command for video composition."""
        
        width = resolution["width"]
        height = resolution["height"]
        
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
        ]
        
        inputs = 1
        
        # Add narration
        if narration_url:
            cmd.extend(["-i", narration_url])
            inputs += 1
        
        # Add background music
        if background_music_url:
            cmd.extend(["-i", background_music_url])
            inputs += 1
        
        # Video filter
        vf_parts = [f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"]
        
        # Add captions if enabled
        if captions_config and captions_config.get("enabled"):
            caption_filter = self._build_caption_filter(captions_config, width, height)
            vf_parts.append(caption_filter)
        
        cmd.extend(["-vf", ",".join(vf_parts)])
        
        # Audio filter
        if narration_url or background_music_url:
            af_parts = []
            
            if narration_url and background_music_url:
                # Mix narration and background music
                af_parts.append("[1:a]volume=1.0[na]")
                af_parts.append("[2:a]volume=0.3[bg]")
                af_parts.append("[na][bg]amix=inputs=2:duration=first[aout]")
                cmd.extend(["-filter_complex", ";".join(af_parts)])
                cmd.extend(["-map", "0:v", "-map", "[aout]"])
            elif narration_url:
                cmd.extend(["-map", "0:v", "-map", "1:a"])
            else:
                cmd.extend(["-map", "0:v", "-map", "2:a"])
        
        # Output settings
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            output_path,
        ])
        
        return cmd
    
    def _build_caption_filter(
        self,
        config: Dict,
        width: int,
        height: int,
    ) -> str:
        """Build FFmpeg filter for captions."""
        
        style = config.get("style", "modern")
        color = config.get("color", "white")
        
        # Font settings based on style
        fonts = {
            "modern": "Montserrat-Bold",
            "classic": "Georgia-Bold",
            "bold": "Impact",
            "minimal": "Inter-Bold",
            "fun": "Comic-Sans-MS",
        }
        
        font = fonts.get(style, "Montserrat-Bold")
        
        # Build drawtext filter
        # Note: This is simplified. Real implementation would need
        # to handle caption timing and positioning more carefully
        
        fontsize = int(height * 0.05)  # 5% of video height
        y_position = int(height * 0.85)  # 85% from top
        
        # This is a placeholder - real implementation would need
        # to process caption timing from scene data
        caption_filter = (
            f"drawtext=fontfile={font}:"
            f"text='Sample Caption':"
            f"fontsize={fontsize}:"
            f"fontcolor={color}:"
            f"x=(w-text_w)/2:"
            f"y={y_position}:"
            f"borderw=2:"
            f"bordercolor=black@0.5"
        )
        
        return caption_filter
    
    async def _run_ffmpeg(self, cmd: List[str]) -> None:
        """Execute FFmpeg command."""
        
        logger.info("Running FFmpeg", command=" ".join(cmd))
        
        process = await subprocess.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error("FFmpeg failed", error=error_msg)
            raise RuntimeError(f"FFmpeg failed: {error_msg}")
        
        logger.info("FFmpeg completed successfully")
    
    def _cleanup(self, work_dir: str) -> None:
        """Clean up temporary files."""
        
        import shutil
        
        try:
            shutil.rmtree(work_dir)
        except Exception as e:
            logger.warning("Cleanup failed", error=str(e))
    
    async def generate_thumbnail(
        self,
        video_url: str,
        time_offset: float = 1.0,
    ) -> str:
        """Generate thumbnail from video."""
        
        work_dir = tempfile.mkdtemp(dir=self.temp_dir)
        
        try:
            # Download video
            video_path = os.path.join(work_dir, "video.mp4")
            video_data = await self.storage.download_file(video_url)
            
            with open(video_path, "wb") as f:
                f.write(video_data)
            
            # Extract frame
            thumbnail_path = os.path.join(work_dir, "thumbnail.jpg")
            
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss", str(time_offset),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                thumbnail_path,
            ]
            
            await self._run_ffmpeg(cmd)
            
            # Upload thumbnail
            with open(thumbnail_path, "rb") as f:
                thumbnail_data = f.read()
            
            thumbnail_url = await self.storage.upload_file(
                file_data=thumbnail_data,
                filename=f"thumbnails/{uuid.uuid4()}.jpg",
                content_type="image/jpeg",
            )
            
            return thumbnail_url
            
        finally:
            self._cleanup(work_dir)
    
    async def get_video_info(self, video_url: str) -> Dict:
        """Get video metadata."""
        
        cmd = [
            self.ffmpeg_path.replace("ffmpeg", "ffprobe"),
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate",
            "-show_entries", "stream=width,height,codec_name",
            "-of", "json",
            video_url,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        import json
        info = json.loads(result.stdout)
        
        return {
            "duration": float(info.get("format", {}).get("duration", 0)),
            "width": info.get("streams", [{}])[0].get("width"),
            "height": info.get("streams", [{}])[0].get("height"),
            "size": int(info.get("format", {}).get("size", 0)),
            "bitrate": int(info.get("format", {}).get("bit_rate", 0)),
          }
