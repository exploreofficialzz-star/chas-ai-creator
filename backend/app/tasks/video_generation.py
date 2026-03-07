"""
Celery tasks for video generation.
Created by: chAs
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from celery import Celery
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.models.video import Video, VideoScene, VideoSchedule, VideoStatus
from app.services.ai.text_generation import TextGenerationService
from app.services.ai.image_generation import ImageGenerationService
from app.services.ai.video_generation import VideoGenerationService
from app.services.ai.voice_generation import VoiceGenerationService
from app.services.video_composer import VideoComposerService
import uuid

logger = get_logger(__name__)

# Initialize Celery
celery_app = Celery(
    "video_generation",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@celery_app.task(bind=True, max_retries=3)
def generate_video_task(self, video_id: str) -> Dict[str, Any]:
    """Main video generation task."""
    
    db = get_db()
    video = None
    
    try:
        # Get video
        video = db.query(Video).filter(Video.id == video_id).first()
        
        if not video:
            logger.error("❌ Video not found", video_id=video_id)
            return {"status": "error", "message": "Video not found"}
        
        # Update status
        video.status = VideoStatus.SCRIPT_GENERATING
        video.started_at = datetime.utcnow()
        video.progress = 5
        db.commit()
        
        logger.info(f"🎬 Starting video generation for {video_id}")
        
        # Initialize services
        text_service = TextGenerationService()
        image_service = ImageGenerationService()
        video_service = VideoGenerationService()
        voice_service = VoiceGenerationService()
        composer_service = VideoComposerService()
        
        # Step 1: Generate script
        logger.info(f"📝 Generating script for video {video_id}")
        
        try:
            # Run async function in sync context
            script = asyncio.run(text_service.generate_script(
                niche=video.niche,
                video_type=video.video_type.value,
                duration=video.duration,
                user_instructions=video.user_instructions,
                style=video.style.value,
            ))
            
            # Update video with script
            video.title = script.get("title", "Untitled Video")
            video.description = script.get("description", "")
            video.script = script
            video.narration_text = script.get("narration")
            video.hashtags = script.get("hashtags", [])
            video.status = VideoStatus.IMAGES_GENERATING
            video.progress = 20
            db.commit()
            
            logger.info(f"✅ Script generated: {video.title}")
            
        except Exception as e:
            logger.error(f"❌ Script generation failed: {e}")
            raise
        
        # Step 2: Generate images for each scene
        logger.info(f"🎨 Generating images for video {video_id}")
        
        scenes = []
        character_consistency = None
        
        if video.character_consistency_enabled and video.character_description:
            character_consistency = video.character_description
        
        script_scenes = script.get("scenes", [])
        
        for i, scene_data in enumerate(script_scenes):
            try:
                # Generate image
                image_url = asyncio.run(image_service.generate_image(
                    prompt=scene_data.get("image_prompt", scene_data.get("description", "")),
                    style=video.style.value,
                    aspect_ratio=video.aspect_ratio,
                    character_consistency=character_consistency,
                ))
                
                # Create scene record
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
                
                # Update progress
                video.progress = 20 + int((i + 1) / max(len(script_scenes), 1) * 30)
                db.commit()
                
                logger.info(f"✅ Image {i+1}/{len(script_scenes)} generated")
                
            except Exception as e:
                logger.error(f"❌ Image generation failed for scene {i+1}: {e}")
                # Continue with other scenes
        
        if not scenes:
            raise Exception("No scenes were generated successfully")
        
        video.status = VideoStatus.VIDEO_GENERATING
        db.commit()
        
        # Step 3: Generate video clips from images
        logger.info(f"🎬 Generating video clips for {video_id}")
        
        for i, scene in enumerate(scenes):
            try:
                video_clip_url = asyncio.run(video_service.generate_video_clip(
                    image_url=scene.image_url,
                    prompt=scene.description,
                    duration=scene.duration,
                ))
                
                scene.video_clip_url = video_clip_url
                video.progress = 50 + int((i + 1) / max(len(scenes), 1) * 20)
                db.commit()
                
                logger.info(f"✅ Video clip {i+1}/{len(scenes)} generated")
                
            except Exception as e:
                logger.error(f"❌ Video clip generation failed for scene {i+1}: {e}")
                # Use image as fallback
                scene.video_clip_url = scene.image_url
                db.commit()
        
        # Step 4: Generate narration if needed
        narration_url = None
        if video.video_type.value == "narration" and video.narration_text:
            logger.info(f"🎤 Generating narration for {video_id}")
            
            video.status = VideoStatus.AUDIO_GENERATING
            db.commit()
            
            try:
                narration_url = asyncio.run(voice_service.generate_voiceover(
                    text=video.narration_text,
                ))
                logger.info("✅ Narration generated")
            except Exception as e:
                logger.error(f"❌ Narration generation failed: {e}")
        
        # Step 5: Compose final video
        logger.info(f"🔧 Composing final video for {video_id}")
        
        video.status = VideoStatus.COMPOSING
        video.progress = 80
        db.commit()
        
        # Prepare scenes for composer
        scene_data = [
            {
                "video_clip_url": s.video_clip_url,
                "image_url": s.image_url,
                "caption": s.caption,
                "duration": s.duration,
            }
            for s in scenes if s.video_clip_url or s.image_url
        ]
        
        if not scene_data:
            raise Exception("No valid scenes to compose")
        
        # Compose video
        try:
            final_video_url = asyncio.run(composer_service.compose_video(
                scenes=scene_data,
                narration_url=narration_url,
                background_music_url=None,  # Would be fetched from music library
                captions_config={
                    "enabled": video.captions_enabled,
                    "style": video.caption_style,
                    "color": video.caption_color,
                },
                aspect_ratio=video.aspect_ratio,
            ))
            
            # Generate thumbnail
            thumbnail_url = asyncio.run(composer_service.generate_thumbnail(final_video_url))
            
            # Update video
            video.video_url = final_video_url
            video.thumbnail_url = thumbnail_url
            video.status = VideoStatus.COMPLETED
            video.progress = 100
            video.completed_at = datetime.utcnow()
            
            # Get video info
            try:
                video_info = asyncio.run(composer_service.get_video_info(final_video_url))
                video.file_size = video_info.get("size")
                video.resolution = f"{video_info.get('width')}x{video_info.get('height')}"
            except Exception as e:
                logger.warning(f"Could not get video info: {e}")
            
            db.commit()
            
            logger.info(f"✅ Video generation completed: {video_id}")
            
            return {
                "status": "success",
                "video_id": video_id,
                "video_url": final_video_url,
                "thumbnail_url": thumbnail_url,
            }
            
        except Exception as e:
            logger.error(f"❌ Video composition failed: {e}")
            raise
        
    except Exception as e:
        logger.error(f"❌ Video generation failed: {e}", video_id=video_id)
        
        # Update video status
        if video:
            video.status = VideoStatus.FAILED
            video.error_message = str(e)
            db.commit()
        
        # Retry on failure
        try:
            self.retry(exc=e, countdown=60)
        except Exception:
            pass
        
        return {
            "status": "error",
            "video_id": video_id,
            "error": str(e)
        }
        
    finally:
        db.close()


@celery_app.task
def process_scheduled_videos() -> Dict[str, Any]:
    """Process scheduled video generation tasks."""
    
    db = get_db()
    
    try:
        from datetime import datetime
        
        # Get all active schedules
        schedules = db.query(VideoSchedule).filter(
            VideoSchedule.is_active == True
        ).all()
        
        videos_queued = 0
        
        for schedule in schedules:
            if not schedule.can_generate_today():
                continue
            
            # Check if it's time to generate
            current_time = datetime.utcnow().strftime("%H:%M")
            
            if current_time in schedule.schedule_times:
                # Create video from schedule
                video_config = schedule.video_config or {}
                
                video = Video(
                    id=str(uuid.uuid4()),
                    user_id=schedule.user_id,
                    niche=video_config.get("niche", "general"),
                    video_type=video_config.get("video_type", "silent"),
                    duration=video_config.get("duration", 30),
                    aspect_ratio=video_config.get("aspect_ratio", "9:16"),
                    style=video_config.get("style", "cinematic"),
                    is_scheduled=True,
                    schedule_id=schedule.id,
                    status=VideoStatus.PENDING,
                )
                
                db.add(video)
                
                # Update schedule
                schedule.videos_generated_today += 1
                schedule.total_videos_generated += 1
                schedule.last_generated_at = datetime.utcnow()
                
                db.commit()
                
                # Queue generation
                generate_video_task.delay(video.id)
                
                videos_queued += 1
                logger.info(f"📅 Scheduled video queued: {video.id}")
        
        logger.info(f"📅 Scheduled videos processed: {videos_queued} queued")
        
        return {"status": "success", "videos_queued": videos_queued}
        
    except Exception as e:
        logger.error(f"❌ Scheduled video processing failed: {e}")
        return {"status": "error", "error": str(e)}
        
    finally:
        db.close()


@celery_app.task
def reset_daily_video_counts() -> None:
    """Reset daily video counts for all schedules."""
    
    db = get_db()
    
    try:
        schedules = db.query(VideoSchedule).all()
        
        for schedule in schedules:
            schedule.reset_daily_count()
        
        db.commit()
        
        logger.info("✅ Daily video counts reset")
        
    except Exception as e:
        logger.error(f"❌ Daily count reset failed: {e}")
        
    finally:
        db.close()


@celery_app.task
def cleanup_old_videos() -> None:
    """Clean up videos past auto-delete date."""
    
    db = get_db()
    
    try:
        from datetime import datetime, timedelta
        from app.models.user import UserSettings
        
        # Find users with auto-delete enabled
        settings_with_auto_delete = db.query(UserSettings).filter(
            UserSettings.auto_delete_videos_days != None
        ).all()
        
        deleted_count = 0
        
        for user_settings in settings_with_auto_delete:
            cutoff_date = datetime.utcnow() - timedelta(
                days=user_settings.auto_delete_videos_days
            )
            
            # Find old videos
            old_videos = db.query(Video).filter(
                Video.user_id == user_settings.user_id,
                Video.created_at < cutoff_date,
                Video.status == VideoStatus.COMPLETED,
            ).all()
            
            for video in old_videos:
                # Delete from storage (implement as needed)
                # storage.delete_file(video.video_url)
                # storage.delete_file(video.thumbnail_url)
                
                # Delete from database
                db.delete(video)
                deleted_count += 1
            
            db.commit()
        
        logger.info(f"🗑️ Cleaned up {deleted_count} old videos")
        
    except Exception as e:
        logger.error(f"❌ Old video cleanup failed: {e}")
        
    finally:
        db.close()
