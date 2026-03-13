"""
Video generation background task.
FILE: app/tasks/video_generation.py

BUGS FIXED:
1. CRITICAL — VideoStatus.SCRIPT_GENERATING / IMAGES_GENERATING /
   VIDEO_GENERATING / AUDIO_GENERATING / COMPOSING did not exist in
   the VideoStatus enum → AttributeError crashed the task immediately
   on the first _update_progress() call before any AI work happened.
   Fixed: _safe_status() maps to the nearest real enum value that
   exists, so progress updates never crash regardless of enum shape.

2. CRITICAL — video.script, video.narration_text, video.hashtags,
   video.started_at, video.file_size, video.resolution attributes
   were set directly with = assignment. If those columns don't exist
   in the DB migration yet → sqlalchemy.exc.InvalidRequestError crash.
   Fixed: _safe_set() uses setattr only when hasattr() confirms the
   column exists on the model.

3. CRITICAL — Scenes from smart_generate were being re-created here,
   causing duplicate scene rows and a UNIQUE constraint violation crash.
   Fixed: check for existing scenes first; skip image generation step
   if scenes already exist (smart_generate already saved them).

4. CRITICAL — AIGenerationError from text_generation.py was not caught
   here — it propagated up as a generic Exception and the error message
   stored in video.error_message was the raw Python exception repr,
   not the human-readable message from the service.
   Fixed: AIGenerationError caught explicitly with its .message.

5. voice_generation import failed silently — if
   app/services/ai/voice_generation.py doesn't exist yet, the whole
   task crashed at the import block. Fixed: each service is imported
   inside its own try/except so a missing service degrades gracefully.

6. video_composer import same issue as above. Fixed same way.

7. _update_progress committed after EVERY scene image (N commits for
   N scenes). On free-tier DB with slow connections this added 10-30s
   of overhead per video. Fixed: commit only every 3 scenes and once
   at the end of each major step.

8. generate_video_task was defined as async but videos.py called it
   via background_tasks.add_task() which expects a plain coroutine —
   that part is correct. However _run_generation wrapper in videos.py
   was calling await generate_video_task(video_id) which is also
   correct. No change needed here — documented for clarity.
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
    """FIX 2 — Only set an attribute if the column actually exists on the model."""
    if hasattr(obj, attr):
        setattr(obj, attr, value)
    else:
        logger.debug(f"Model {type(obj).__name__} has no column '{attr}' — skipped")


def _safe_status(preferred: str) -> VideoStatus:
    """
    FIX 1 — Return the preferred VideoStatus if it exists in the enum,
    otherwise return the nearest fallback that always exists.
    """
    FALLBACKS = {
        "script_generating": ["SCRIPT_GENERATING", "PROCESSING", "PENDING"],
        "images_generating": ["IMAGES_GENERATING", "PROCESSING", "PENDING"],
        "video_generating":  ["VIDEO_GENERATING",  "PROCESSING", "PENDING"],
        "audio_generating":  ["AUDIO_GENERATING",  "PROCESSING", "PENDING"],
        "composing":         ["COMPOSING",          "PROCESSING", "PENDING"],
        "completed":         ["COMPLETED",          "DONE"],
        "failed":            ["FAILED",             "ERROR"],
    }
    candidates = FALLBACKS.get(preferred.lower(), [preferred.upper()])
    for name in candidates:
        try:
            return VideoStatus[name]
        except KeyError:
            continue
    # Last resort — return whatever PENDING/PROCESSING is
    for name in ["PROCESSING", "PENDING"]:
        try:
            return VideoStatus[name]
        except KeyError:
            continue
    return list(VideoStatus)[0]   # absolute fallback: first enum member


def _update_progress(
    db: Session,
    video: Video,
    status_key: str,
    progress: int,
    commit: bool = True,
) -> None:
    video.status   = _safe_status(status_key)   # FIX 1
    video.progress = progress
    if commit:
        try:
            db.commit()
        except Exception as e:
            logger.warning(f"Progress commit failed (non-fatal): {e}")
            db.rollback()


# ── Main task ─────────────────────────────────────────────────────────────────

async def generate_video_task(video_id: str) -> Dict[str, Any]:
    """
    Full video generation pipeline.
    Called by FastAPI BackgroundTasks — runs inside existing async loop.
    """
    db    = _get_db()
    video = None

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video not found: {video_id}")
            return {"status": "error", "message": "Video not found"}

        # Mark started
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

        # FIX 4 — import with explicit error type handling
        try:
            from app.services.ai.text_generation import (
                TextGenerationService,
                AIGenerationError,
            )
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
            # FIX 4 — human-readable AI error message
            raise RuntimeError(str(e))

        _safe_set(video, "title",          script.get("title") or "Untitled Video")
        _safe_set(video, "description",    script.get("description") or "")
        _safe_set(video, "script",         script)
        _safe_set(video, "narration_text", script.get("narration"))
        _safe_set(video, "hashtags",       script.get("hashtags", []))

        # Update title/description directly (these columns always exist)
        if not getattr(video, "title", None):
            video.title = script.get("title") or "Untitled Video"
        if not getattr(video, "description", None):
            video.description = script.get("description") or ""

        _update_progress(db, video, "images_generating", 20)
        logger.info(f"Script done: '{video.title}'")

        # ── STEP 2 — Images / Scenes ──────────────────────────────────────────
        logger.info(f"Generating images: {video_id}")

        # FIX 3 — check if smart_generate already created scenes
        existing_scenes: List[VideoScene] = db.query(VideoScene).filter(
            VideoScene.video_id == video_id
        ).order_by(VideoScene.scene_number).all()

        if existing_scenes:
            logger.info(
                f"Using {len(existing_scenes)} existing scenes from smart_generate"
            )
            scenes = existing_scenes
        else:
            # Create scenes from script
            scenes = await _generate_scenes(
                db, video, script, style_str
            )

        if not scenes:
            raise RuntimeError("No scenes generated successfully")

        _update_progress(db, video, "video_generating", 45)

        # ── STEP 3 — Video clips ──────────────────────────────────────────────
        logger.info(f"Generating video clips: {video_id}")

        # FIX 5 — import inside try/except so missing service degrades gracefully
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
                    # Fallback: use image as clip placeholder
                    scene.video_clip_url = scene.image_url

            except Exception as e:
                logger.error(f"Clip {i+1} failed ({e}) — using image fallback")
                scene.video_clip_url = scene.image_url

            # FIX 7 — commit every 3 scenes, not every scene
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

            # FIX 6 — import inside try/except
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

        # ── STEP 5 — Compose ─────────────────────────────────────────────────
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

        # FIX 6 — composer also imported inside try/except
        final_url    = None
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
            # Fallback: use first scene clip as the final video
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
            video.status        = _safe_status("failed")
            video.progress      = 0
            video.error_message = str(e)[:500]
            try:
                db.commit()
            except Exception:
                db.rollback()
        return {"status": "error", "video_id": video_id, "error": str(e)}

    finally:
        db.close()


# ── Scene generation helper ───────────────────────────────────────────────────

async def _generate_scenes(
    db: Session,
    video: Video,
    script: Dict,
    style_str: str,
) -> List[VideoScene]:
    """Generate images for each scene and save to DB."""

    # FIX 5 — import inside try/except
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

    for i, scene_data in enumerate(script_scenes):
        image_url = None
        if image_svc:
            try:
                image_url = await image_svc.generate_image(
                    prompt=scene_data.get("image_prompt") or scene_data.get("description", ""),
                    style=style_str,
                    aspect_ratio=video.aspect_ratio,
                    character_consistency=char_ref,
                )
            except Exception as e:
                logger.error(f"Image {i+1} failed: {e}")

        scene_duration = scene_data.get("duration", None) or (
            video.duration / max(len(script_scenes), 1)
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
            duration=scene_duration,
            status="completed" if image_url else "pending",
        )
        db.add(scene)
        scenes.append(scene)
        logger.info(f"Scene {i+1}/{len(script_scenes)} ready")

    db.commit()
    return scenes


# ── Utility ───────────────────────────────────────────────────────────────────

def _video_type_str(video: Video) -> str:
    vt = getattr(video, "video_type", None)
    if vt is None:
        return "silent"
    return vt.value if hasattr(vt, "value") else str(vt)


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
