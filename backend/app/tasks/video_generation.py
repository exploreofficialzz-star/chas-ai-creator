"""
Video generation background task.
FILE: app/tasks/video_generation.py

FIXES:
1. CRITICAL — Original used Celery which requires Redis. Render free tier
   has NO Redis. Celery workers would never start. Replaced with a plain
   async function that FastAPI's BackgroundTasks calls directly.

2. CRITICAL — asyncio.run() inside a Celery task crashes with
   "This event loop is already running." FastAPI runs in an async event
   loop — all AI service calls are now awaited directly (no asyncio.run).

3. video_type "sound_sync" (from frontend AudioMode.soundSync) was not
   handled — only "silent" and "narration" existed. Added sound_sync path.

4. Voice style from frontend (professional/friendly/dramatic/energetic/
   calm/authoritative) is now passed to voice_generation service.

5. Target platforms stored on video are now used to generate platform-
   specific captions and hashtags via text_generation service.

6. Progress updates are committed at each stage so the Flutter app can
   poll GET /{video_id} and show real-time progress to the user.

7. Scheduled video task and cleanup tasks kept as plain async functions
   — can be called from an APScheduler job if needed later.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.models.video import Video, VideoScene, VideoSchedule, VideoStatus

logger = get_logger(__name__)


# ─── DB HELPER ────────────────────────────────────────────────────────────────

def _get_db() -> Session:
    return SessionLocal()


def _update_progress(
    db: Session,
    video: Video,
    status: VideoStatus,
    progress: int,
    commit: bool = True,
) -> None:
    """Update video status + progress and optionally commit."""
    video.status   = status
    video.progress = progress
    if commit:
        db.commit()


# ─── MAIN GENERATION TASK ────────────────────────────────────────────────────
# Called by FastAPI BackgroundTasks — runs inside the existing async event
# loop so all awaits work correctly.

async def generate_video_task(video_id: str) -> Dict[str, Any]:
    """
    Full video generation pipeline:
      1. Generate script  (text_generation)
      2. Generate images  (image_generation)
      3. Generate clips   (video_generation)
      4. Generate voice   (voice_generation) — narration / sound_sync only
      5. Compose final    (video_composer)
    """
    db    = _get_db()
    video = None

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"❌ Video not found: {video_id}")
            return {"status": "error", "message": "Video not found"}

        # ── Mark started ──────────────────────────────────────────────────
        video.started_at = datetime.utcnow()
        _update_progress(db, video, VideoStatus.SCRIPT_GENERATING, 5)
        logger.info(f"🎬 Generation started: {video_id} | "
                    f"niche={video.niche} | audio={getattr(video, 'audio_mode', 'silent')}")

        # ── Import services ───────────────────────────────────────────────
        from app.services.ai.text_generation  import TextGenerationService
        from app.services.ai.image_generation import ImageGenerationService
        from app.services.ai.video_generation import VideoGenerationService
        from app.services.ai.voice_generation import VoiceGenerationService
        from app.services.video_composer      import VideoComposerService

        text_svc     = TextGenerationService()
        image_svc    = ImageGenerationService()
        video_svc    = VideoGenerationService()
        voice_svc    = VoiceGenerationService()
        composer_svc = VideoComposerService()

        # ── Audio mode ────────────────────────────────────────────────────
        audio_mode  = getattr(video, "audio_mode", None) \
                      or (video.video_type.value
                          if hasattr(video.video_type, "value")
                          else str(video.video_type))
        voice_style = getattr(video, "voice_style", "professional") or "professional"
        target_platforms = getattr(video, "target_platforms", ["tiktok"]) or ["tiktok"]

        # ── STEP 1 — Script ───────────────────────────────────────────────
        logger.info(f"📝 Generating script: {video_id}")
        script = await text_svc.generate_script(
            niche=video.niche,
            video_type=audio_mode,
            duration=video.duration,
            user_instructions=video.user_instructions,
            style=video.style.value
                  if hasattr(video.style, "value") else str(video.style),
            aspect_ratio=video.aspect_ratio,
            target_platforms=target_platforms,
            voice_style=voice_style,
        )

        video.title          = script.get("title") or "Untitled Video"
        video.description    = script.get("description") or ""
        video.script         = script
        video.narration_text = script.get("narration")
        video.hashtags       = script.get("hashtags", [])
        _update_progress(db, video, VideoStatus.IMAGES_GENERATING, 20)
        logger.info(f"✅ Script done: '{video.title}'")

        # ── STEP 2 — Images ───────────────────────────────────────────────
        logger.info(f"🎨 Generating images: {video_id}")
        script_scenes = script.get("scenes", [])
        character_ref = (
            video.character_description
            if video.character_consistency_enabled
            else None
        )

        scenes: list[VideoScene] = []

        for i, scene_data in enumerate(script_scenes):
            try:
                image_url = await image_svc.generate_image(
                    prompt=scene_data.get(
                        "image_prompt",
                        scene_data.get("description", "")
                    ),
                    style=video.style.value
                          if hasattr(video.style, "value") else str(video.style),
                    aspect_ratio=video.aspect_ratio,
                    character_consistency=character_ref,
                )

                scene = VideoScene(
                    id=str(uuid.uuid4()),
                    video_id=video.id,
                    scene_number=scene_data.get("scene_number", i + 1),
                    description=scene_data.get("description", ""),
                    caption=scene_data.get("caption"),
                    narration=scene_data.get("narration"),
                    image_url=image_url,
                    image_prompt=scene_data.get("image_prompt", ""),
                    duration=video.duration / max(len(script_scenes), 1),
                    status="completed",
                )
                db.add(scene)
                scenes.append(scene)

                progress = 20 + int((i + 1) / max(len(script_scenes), 1) * 25)
                _update_progress(db, video, VideoStatus.IMAGES_GENERATING, progress)
                logger.info(f"✅ Image {i + 1}/{len(script_scenes)}")

            except Exception as e:
                logger.error(f"❌ Image {i + 1} failed: {e}")
                # Continue — partial scenes are better than failing entirely

        if not scenes:
            raise Exception("No scenes generated successfully")

        _update_progress(db, video, VideoStatus.VIDEO_GENERATING, 45)

        # ── STEP 3 — Video clips ──────────────────────────────────────────
        logger.info(f"🎬 Generating video clips: {video_id}")

        for i, scene in enumerate(scenes):
            try:
                clip_url = await video_svc.generate_video_clip(
                    image_url=scene.image_url,
                    prompt=scene.description,
                    duration=scene.duration,
                )
                scene.video_clip_url = clip_url

            except Exception as e:
                logger.error(f"❌ Clip {i + 1} failed: {e} — using image fallback")
                scene.video_clip_url = scene.image_url  # image fallback

            progress = 45 + int((i + 1) / max(len(scenes), 1) * 20)
            _update_progress(db, video, VideoStatus.VIDEO_GENERATING, progress)

        # ── STEP 4 — Voice / Audio ────────────────────────────────────────
        narration_url: Optional[str] = None

        if audio_mode in ("narration", "sound_sync") and video.narration_text:
            logger.info(f"🎤 Generating voice: {video_id} | style={voice_style}")
            _update_progress(db, video, VideoStatus.AUDIO_GENERATING, 70)

            try:
                narration_url = await voice_svc.generate_voiceover(
                    text=video.narration_text,
                    voice_style=voice_style,          # FIX 4 — was ignored
                )
                logger.info("✅ Voiceover generated")
            except Exception as e:
                logger.error(f"❌ Voice generation failed: {e} — continuing without audio")

        # ── STEP 5 — Compose ──────────────────────────────────────────────
        logger.info(f"🔧 Composing final video: {video_id}")
        _update_progress(db, video, VideoStatus.COMPOSING, 80)

        scene_data_list = [
            {
                "video_clip_url": s.video_clip_url,
                "image_url":      s.image_url,
                "caption":        s.caption,
                "narration":      s.narration,
                "duration":       s.duration,
            }
            for s in scenes
            if s.video_clip_url or s.image_url
        ]

        if not scene_data_list:
            raise Exception("No valid scene media to compose")

        final_url = await composer_svc.compose_video(
            scenes=scene_data_list,
            narration_url=narration_url,
            background_music_url=None,
            captions_config={
                "enabled": video.captions_enabled,
                "style":   video.caption_style,
                "color":   video.caption_color,
                "emoji":   video.caption_emoji_enabled,
            },
            aspect_ratio=video.aspect_ratio,
            audio_mode=audio_mode,
        )

        # Thumbnail
        try:
            thumbnail_url = await composer_svc.generate_thumbnail(final_url)
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {e}")
            thumbnail_url = scenes[0].image_url if scenes else None

        # Video metadata
        try:
            info = await composer_svc.get_video_info(final_url)
            video.file_size  = info.get("size")
            video.resolution = f"{info.get('width')}x{info.get('height')}"
        except Exception:
            pass

        # ── Complete ──────────────────────────────────────────────────────
        video.video_url     = final_url
        video.thumbnail_url = thumbnail_url
        video.completed_at  = datetime.utcnow()
        _update_progress(db, video, VideoStatus.COMPLETED, 100)

        logger.info(f"✅ Video complete: {video_id} → {final_url}")

        return {
            "status":        "success",
            "video_id":      video_id,
            "video_url":     final_url,
            "thumbnail_url": thumbnail_url,
        }

    except Exception as e:
        logger.error(f"❌ Video generation failed: {video_id} — {e}")

        if video:
            video.status        = VideoStatus.FAILED
            video.error_message = str(e)
            try:
                db.commit()
            except Exception:
                db.rollback()

        return {"status": "error", "video_id": video_id, "error": str(e)}

    finally:
        db.close()


# ─── SCHEDULED VIDEO PROCESSOR ───────────────────────────────────────────────
# Call this from APScheduler or a cron endpoint — no Redis needed.

async def process_scheduled_videos() -> Dict[str, Any]:
    """Check active schedules and queue any videos due right now."""
    db = _get_db()
    try:
        schedules = db.query(VideoSchedule).filter(
            VideoSchedule.is_active == True
        ).all()

        queued = 0
        current_time = datetime.utcnow().strftime("%H:%M")

        for schedule in schedules:
            if not schedule.can_generate_today():
                continue
            if current_time not in (schedule.schedule_times or []):
                continue

            config = schedule.video_config or {}

            video = Video(
                id=str(uuid.uuid4()),
                user_id=schedule.user_id,
                niche=config.get("niche", "general"),
                video_type=config.get("video_type", "silent"),
                audio_mode=config.get("audio_mode", "silent"),
                duration=config.get("duration", 30),
                aspect_ratio=config.get("aspect_ratio", "9:16"),
                style=config.get("style", "cinematic"),
                captions_enabled=config.get("captions_enabled", True),
                background_music_enabled=config.get("background_music_enabled", True),
                is_scheduled=True,
                schedule_id=schedule.id,
                status=VideoStatus.PENDING,
                progress=0,
            )
            db.add(video)

            schedule.videos_generated_today += 1
            schedule.total_videos_generated += 1
            schedule.last_generated_at = datetime.utcnow()
            db.commit()

            # Fire and forget inside the running loop
            asyncio.create_task(generate_video_task(video.id))
            queued += 1
            logger.info(f"📅 Scheduled video queued: {video.id}")

        logger.info(f"📅 {queued} scheduled videos queued")
        return {"status": "success", "videos_queued": queued}

    except Exception as e:
        logger.error(f"❌ Scheduled video processing failed: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


async def reset_daily_video_counts() -> None:
    """Reset daily video counts for all schedules (call at midnight UTC)."""
    db = _get_db()
    try:
        schedules = db.query(VideoSchedule).all()
        for s in schedules:
            s.reset_daily_count()
        db.commit()
        logger.info("✅ Daily video counts reset")
    except Exception as e:
        logger.error(f"❌ Daily count reset failed: {e}")
    finally:
        db.close()


async def cleanup_old_videos() -> None:
    """Delete videos past each user's auto-delete setting."""
    db = _get_db()
    try:
        from datetime import timedelta
        from app.models.user import UserSettings

        settings_rows = db.query(UserSettings).filter(
            UserSettings.auto_delete_videos_days != None
        ).all()

        deleted = 0
        for us in settings_rows:
            cutoff = datetime.utcnow() - timedelta(days=us.auto_delete_videos_days)
            old = db.query(Video).filter(
                Video.user_id == us.user_id,
                Video.created_at < cutoff,
                Video.status == VideoStatus.COMPLETED,
            ).all()
            for v in old:
                db.delete(v)
                deleted += 1
        db.commit()
        logger.info(f"🗑️ Cleaned up {deleted} old videos")

    except Exception as e:
        logger.error(f"❌ Old video cleanup failed: {e}")
    finally:
        db.close()
