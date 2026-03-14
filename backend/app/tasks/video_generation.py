"""
Video generation background task.
FILE: app/tasks/video_generation.py

FIXES:
1. psycopg2.OperationalError — server closed the connection unexpectedly.
   Supabase closes idle connections after ~5 minutes. With 10 scenes × ~60s
   each, the connection dies before the bulk INSERT. Fixed by committing
   each scene individually and reconnecting when needed.

2. DetachedInstanceError — after _generate_scenes() reconnects to a new
   session, VideoScene objects are detached. Step 3 reading scene.image_url
   crashes with "Instance is not bound to a Session".
   Fixed: after _generate_scenes() returns, immediately re-query all scenes
   from the new db session so they are properly attached.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.models.video import Video, VideoScene, VideoSchedule, VideoStatus

logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db() -> Session:
    return SessionLocal()


def _safe_set(obj: Any, attr: str, value: Any) -> None:
    """Only set an attribute if the column actually exists on the model."""
    if hasattr(obj, attr):
        setattr(obj, attr, value)
    else:
        logger.debug(f"Model {type(obj).__name__} has no column '{attr}' — skipped")


def _safe_status(preferred: str) -> VideoStatus:
    FALLBACKS = {
        "script_generating": ["SCRIPT_GENERATING", "PENDING"],
        "images_generating": ["IMAGES_GENERATING", "PENDING"],
        "video_generating":  ["VIDEO_GENERATING",  "PENDING"],
        "audio_generating":  ["AUDIO_GENERATING",  "PENDING"],
        "composing":         ["COMPOSING",          "PENDING"],
        "completed":         ["COMPLETED"],
        "failed":            ["FAILED"],
        "cancelled":         ["CANCELLED"],
        "pending":           ["PENDING"],
    }
    candidates = FALLBACKS.get(preferred.lower(), [preferred.upper()])
    for name in candidates:
        try:
            return VideoStatus[name]
        except KeyError:
            continue
    for name in ["PENDING", "FAILED"]:
        try:
            return VideoStatus[name]
        except KeyError:
            continue
    return list(VideoStatus)[0]


def _update_progress(
    db: Session,
    video: Video,
    status_key: str,
    progress: int,
    commit: bool = True,
) -> None:
    video.status   = _safe_status(status_key)
    video.progress = progress
    if commit:
        try:
            db.commit()
        except Exception as e:
            logger.warning(f"Progress commit failed (non-fatal): {e}")
            db.rollback()


def _video_type_str(video: Video) -> str:
    vt = getattr(video, "video_type", None)
    if vt is None:
        return "silent"
    return vt.value if hasattr(vt, "value") else str(vt)


def _reconnect_if_needed(db: Session) -> Session:
    """
    Test connection health and return fresh session if dead.
    Supabase closes idle connections after ~5 minutes.
    """
    try:
        db.execute("SELECT 1")
        return db
    except Exception:
        logger.warning("DB connection lost — opening fresh session")
        try:
            db.close()
        except Exception:
            pass
        return SessionLocal()


# ── Main task ─────────────────────────────────────────────────────────────────

async def generate_video_task(video_id: str) -> Dict[str, Any]:
    """
    Full video generation pipeline.
    Always returns a dict — never raises. Caller checks result["status"].
    """
    db    = _get_db()
    video = None

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video not found: {video_id}")
            return {"status": "error", "message": "Video not found"}

        _safe_set(video, "started_at", datetime.utcnow())
        _update_progress(db, video, "script_generating", 5)

        audio_mode       = getattr(video, "audio_mode", None) or _video_type_str(video)
        voice_style      = getattr(video, "voice_style", "professional") or "professional"
        target_platforms = getattr(video, "target_platforms", ["tiktok"]) or ["tiktok"]
        style_str        = video.style.value if hasattr(video.style, "value") else str(video.style)

        logger.info(
            f"Generation started: {video_id} | niche={video.niche} "
            f"audio={audio_mode} style={style_str}"
        )

        # ── STEP 1 — Script ───────────────────────────────────────────────────
        logger.info(f"Generating script: {video_id}")

        try:
            from app.services.ai.text_generation import TextGenerationService, AIGenerationError
            text_svc = TextGenerationService()
        except ImportError as e:
            raise RuntimeError(f"TextGenerationService not available: {e}")

        try:
            script = await text_svc.generate_script(
                niche=video.niche,
                video_type=audio_mode,
                duration=video.duration,
                user_instructions=video.user_instructions,
                style=style_str,
                aspect_ratio=video.aspect_ratio,
                target_platforms=target_platforms,
                voice_style=voice_style,
            )
        except AIGenerationError as e:
            raise RuntimeError(str(e))

        _safe_set(video, "title",          script.get("title") or "Untitled Video")
        _safe_set(video, "description",    script.get("description") or "")
        _safe_set(video, "script",         script)
        _safe_set(video, "narration_text", script.get("narration"))
        _safe_set(video, "hashtags",       script.get("hashtags", []))

        if not getattr(video, "title", None):
            video.title = script.get("title") or "Untitled Video"
        if not getattr(video, "description", None):
            video.description = script.get("description") or ""

        _update_progress(db, video, "images_generating", 20)
        logger.info(f"Script done: '{video.title}'")

        # ── STEP 2 — Images / Scenes ──────────────────────────────────────────
        logger.info(f"Generating images: {video_id}")

        existing_scenes: List[VideoScene] = db.query(VideoScene).filter(
            VideoScene.video_id == video_id
        ).order_by(VideoScene.scene_number).all()

        if existing_scenes:
            logger.info(f"Using {len(existing_scenes)} existing scenes from smart_generate")
            scenes = existing_scenes
        else:
            # _generate_scenes returns (scenes, db) — db may be a new session
            _, db = await _generate_scenes(db, video, script, style_str)

            # FIX 2 — Re-query scenes from the current session so they are
            # properly attached. The objects returned by _generate_scenes may
            # be detached if a reconnect happened during image generation.
            scenes = db.query(VideoScene).filter(
                VideoScene.video_id == video_id
            ).order_by(VideoScene.scene_number).all()

        if not scenes:
            raise RuntimeError("No scenes generated successfully")

        # Re-fetch video in case session changed
        video = db.query(Video).filter(Video.id == video_id).first()

        _update_progress(db, video, "video_generating", 45)

        # ── STEP 3 — Video clips ──────────────────────────────────────────────
        logger.info(f"Generating video clips: {video_id}")

        video_svc = None
        try:
            from app.services.ai.video_generation import VideoGenerationService
            video_svc = VideoGenerationService()
        except ImportError as e:
            logger.warning(f"VideoGenerationService not available: {e}")

        for i, scene in enumerate(scenes):
            try:
                if video_svc:
                    clip_url = await video_svc.generate_video_clip(
                        image_url=scene.image_url or "",
                        prompt=scene.description or "",
                        duration=scene.duration,
                        aspect_ratio=video.aspect_ratio,
                    )
                    scene.video_clip_url = clip_url
                else:
                    scene.video_clip_url = scene.image_url
            except Exception as e:
                logger.error(f"Clip {i+1} failed ({e}) — using image fallback")
                scene.video_clip_url = scene.image_url

            if (i + 1) % 3 == 0:
                progress = 45 + int((i + 1) / max(len(scenes), 1) * 20)
                _update_progress(db, video, "video_generating", progress)

        db.commit()

        # ── STEP 4 — Voice ────────────────────────────────────────────────────
        narration_url: Optional[str] = None
        narration_text = getattr(video, "narration_text", None)

        if audio_mode in ("narration", "sound_sync") and narration_text:
            logger.info(f"Generating voice: {video_id}")
            _update_progress(db, video, "audio_generating", 70)

            try:
                from app.services.ai.voice_generation import VoiceGenerationService
                voice_svc     = VoiceGenerationService()
                narration_url = await voice_svc.generate_voiceover(
                    text=narration_text,
                    voice_style=voice_style,
                )
                logger.info("Voiceover generated")
            except ImportError:
                logger.warning("VoiceGenerationService not available — skipping audio")
            except Exception as e:
                logger.error(f"Voice generation failed ({e}) — continuing without audio")

        # ── STEP 5 — Compose ──────────────────────────────────────────────────
        logger.info(f"Composing final video: {video_id}")
        _update_progress(db, video, "composing", 80)

        scene_data = [
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

        if not scene_data:
            raise RuntimeError("No valid scene media to compose")

        final_url     = None
        thumbnail_url = None
        try:
            from app.services.video_composer import VideoComposerService
            composer = VideoComposerService()

            final_url = await composer.compose_video(
                scenes=scene_data,
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

            try:
                thumbnail_url = await composer.generate_thumbnail(final_url)
            except Exception as e:
                logger.warning(f"Thumbnail failed: {e}")
                thumbnail_url = scenes[0].image_url if scenes else None

            try:
                info = await composer.get_video_info(final_url)
                _safe_set(video, "file_size",  info.get("size"))
                _safe_set(video, "resolution", f"{info.get('width')}x{info.get('height')}")
            except Exception:
                pass

        except ImportError:
            logger.warning("VideoComposerService not available — using first clip URL")
            final_url     = scenes[0].video_clip_url or scenes[0].image_url
            thumbnail_url = scenes[0].image_url

        if not final_url:
            raise RuntimeError("Video composition produced no output URL")

        # ── Complete ──────────────────────────────────────────────────────────
        video.video_url     = final_url
        video.thumbnail_url = thumbnail_url
        _safe_set(video, "completed_at", datetime.utcnow())
        _update_progress(db, video, "completed", 100)

        logger.info(f"Video complete: {video_id} → {final_url}")
        return {
            "status":        "success",
            "video_id":      video_id,
            "video_url":     final_url,
            "thumbnail_url": thumbnail_url,
        }

    except Exception as e:
        logger.error(f"Video generation FAILED: {video_id} — {e}", exc_info=True)
        if video:
            try:
                db = _reconnect_if_needed(db)
                video2 = db.query(Video).filter(Video.id == video_id).first()
                if video2:
                    video2.status        = _safe_status("failed")
                    video2.progress      = 0
                    video2.error_message = str(e)[:500]
                    db.commit()
            except Exception as e2:
                logger.error(f"Could not save failure status: {e2}")
                try:
                    db.rollback()
                except Exception:
                    pass
        return {"status": "error", "video_id": video_id, "error": str(e)}

    finally:
        db.close()


# ── Scene generation helper ───────────────────────────────────────────────────

async def _generate_scenes(
    db: Session,
    video: Video,
    script: Dict,
    style_str: str,
) -> tuple:
    """
    Generate images for each scene and save to DB one at a time.

    Commits each scene individually to avoid Supabase connection timeout
    on bulk INSERT after ~10 minutes of image generation.

    Returns (scenes_list, db) — db may be a new session if reconnected.
    Note: caller should re-query scenes from db after this returns to
    avoid DetachedInstanceError if a reconnect happened.
    """
    image_svc = None
    try:
        from app.services.ai.image_generation import ImageGenerationService
        image_svc = ImageGenerationService()
    except ImportError as e:
        logger.warning(f"ImageGenerationService not available: {e}")

    script_scenes = script.get("scenes", [])
    scenes: List[VideoScene] = []
    char_ref = (
        getattr(video, "character_description", None)
        if getattr(video, "character_consistency_enabled", False)
        else None
    )
    video_id     = video.id
    aspect_ratio = video.aspect_ratio
    duration     = video.duration

    for i, scene_data in enumerate(script_scenes):
        # Generate image
        image_url = None
        if image_svc:
            try:
                image_url = await image_svc.generate_image(
                    prompt=scene_data.get("image_prompt") or scene_data.get("description", ""),
                    style=style_str,
                    aspect_ratio=aspect_ratio,
                    character_consistency=char_ref,
                )
            except Exception as e:
                logger.error(f"Image {i+1} failed: {e}")

        scene_duration = scene_data.get("duration", None) or (
            duration / max(len(script_scenes), 1)
        )

        scene = VideoScene(
            id=str(uuid.uuid4()),
            video_id=video_id,
            scene_number=scene_data.get("scene_number", i + 1),
            description=scene_data.get("description", ""),
            caption=scene_data.get("caption"),
            narration=scene_data.get("narration"),
            image_url=image_url,
            image_prompt=scene_data.get("image_prompt", ""),
            duration=scene_duration,
            status="completed" if image_url else "pending",
        )

        # Commit each scene individually with reconnect + retry
        committed = False
        for attempt in range(3):
            try:
                db = _reconnect_if_needed(db)
                db.add(scene)
                db.commit()
                committed = True
                break
            except Exception as e:
                logger.warning(f"Scene {i+1} commit attempt {attempt+1} failed: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
                if attempt < 2:
                    try:
                        db.close()
                    except Exception:
                        pass
                    db = SessionLocal()
                    await asyncio.sleep(1.0)

        if committed:
            scenes.append(scene)
            logger.info(f"Scene {i+1}/{len(script_scenes)} ready")
        else:
            logger.error(f"Scene {i+1} failed to save after 3 attempts — skipping")

    return scenes, db


# ── Scheduled tasks ───────────────────────────────────────────────────────────

async def process_scheduled_videos() -> Dict[str, Any]:
    db = _get_db()
    try:
        schedules = db.query(VideoSchedule).filter(
            VideoSchedule.is_active == True
        ).all()
        queued       = 0
        current_time = datetime.utcnow().strftime("%H:%M")

        for schedule in schedules:
            if hasattr(schedule, "can_generate_today") and not schedule.can_generate_today():
                continue
            if current_time not in (schedule.schedule_times or []):
                continue

            config = schedule.video_config or {}
            video  = Video(
                id=str(uuid.uuid4()),
                user_id=schedule.user_id,
                niche=config.get("niche", "general"),
                video_type=config.get("video_type", "silent"),
                duration=config.get("duration", 30),
                aspect_ratio=config.get("aspect_ratio", "9:16"),
                style=config.get("style", "cinematic"),
                captions_enabled=config.get("captions_enabled", True),
                background_music_enabled=config.get("background_music_enabled", True),
                status=VideoStatus.PENDING,
                progress=0,
            )
            _safe_set(video, "audio_mode",   config.get("audio_mode", "silent"))
            _safe_set(video, "is_scheduled", True)
            _safe_set(video, "schedule_id",  schedule.id)
            db.add(video)

            schedule.videos_generated_today = (
                getattr(schedule, "videos_generated_today", 0) + 1
            )
            schedule.total_videos_generated = (
                getattr(schedule, "total_videos_generated", 0) + 1
            )
            _safe_set(schedule, "last_generated_at", datetime.utcnow())
            db.commit()

            asyncio.create_task(generate_video_task(video.id))
            queued += 1
            logger.info(f"Scheduled video queued: {video.id}")

        return {"status": "success", "videos_queued": queued}

    except Exception as e:
        logger.error(f"Scheduled video processing failed: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


async def reset_daily_video_counts() -> None:
    db = _get_db()
    try:
        for s in db.query(VideoSchedule).all():
            if hasattr(s, "reset_daily_count"):
                s.reset_daily_count()
            else:
                _safe_set(s, "videos_generated_today", 0)
        db.commit()
        logger.info("Daily video counts reset")
    except Exception as e:
        logger.error(f"Daily count reset failed: {e}")
    finally:
        db.close()


async def cleanup_old_videos() -> None:
    db = _get_db()
    try:
        from datetime import timedelta
        from app.models.user import UserSettings

        deleted = 0
        for us in db.query(UserSettings).filter(
            UserSettings.auto_delete_videos_days != None
        ).all():
            cutoff = datetime.utcnow() - timedelta(days=us.auto_delete_videos_days)
            old    = db.query(Video).filter(
                Video.user_id    == us.user_id,
                Video.created_at < cutoff,
                Video.status     == _safe_status("completed"),
            ).all()
            for v in old:
                db.delete(v)
                deleted += 1
        db.commit()
        logger.info(f"Cleaned up {deleted} old videos")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
    finally:
        db.close()
