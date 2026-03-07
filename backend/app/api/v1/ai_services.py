"""AI services API routes."""

from typing import Optional, List

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationException, AIServiceException
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User
from app.services.ai.text_generation import TextGenerationService
from app.services.ai.image_generation import ImageGenerationService

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get current user
def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("User not found")
    
    return user


# Request/Response Models
class GenerateScriptRequest(BaseModel):
    niche: str
    video_type: str = "silent"
    duration: int = 30
    user_instructions: Optional[str] = None
    style: str = "cinematic"


class GenerateScriptResponse(BaseModel):
    title: str
    description: str
    scenes: List[dict]
    narration: Optional[str]
    hashtags: List[str]


class GenerateImageRequest(BaseModel):
    prompt: str
    style: str = "cinematic"
    aspect_ratio: str = "9:16"
    negative_prompt: Optional[str] = None


class GenerateImageResponse(BaseModel):
    image_url: str
    prompt: str


class PreviewVideoRequest(BaseModel):
    niche: str
    video_type: str = "silent"
    duration: int = 30
    style: str = "cinematic"
    user_instructions: Optional[str] = None


@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(
    request: GenerateScriptRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate video script preview."""
    try:
        text_service = TextGenerationService()
        
        script = await text_service.generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
        )
        
        logger.info(
            "Script generated",
            user_id=current_user.id,
            niche=request.niche,
        )
        
        return GenerateScriptResponse(
            title=script["title"],
            description=script["description"],
            scenes=script["scenes"],
            narration=script.get("narration"),
            hashtags=script.get("hashtags", []),
        )
        
    except Exception as e:
        logger.error("Script generation failed", error=str(e))
        raise AIServiceException("Failed to generate script")


@router.post("/generate-image")
async def generate_image(
    request: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate image preview."""
    try:
        image_service = ImageGenerationService()
        
        image_url = await image_service.generate_image(
            prompt=request.prompt,
            style=request.style,
            aspect_ratio=request.aspect_ratio,
            negative_prompt=request.negative_prompt,
        )
        
        logger.info("Image generated", user_id=current_user.id)
        
        return GenerateImageResponse(
            image_url=image_url,
            prompt=request.prompt,
        )
        
    except Exception as e:
        logger.error("Image generation failed", error=str(e))
        raise AIServiceException("Failed to generate image")


@router.post("/preview-video")
async def preview_video(
    request: PreviewVideoRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate video preview (script + sample images)."""
    try:
        text_service = TextGenerationService()
        image_service = ImageGenerationService()
        
        # Generate script
        script = await text_service.generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
        )
        
        # Generate sample images for first 3 scenes
        sample_images = []
        for scene in script["scenes"][:3]:
            image_url = await image_service.generate_image(
                prompt=scene["image_prompt"],
                style=request.style,
                aspect_ratio="9:16",
            )
            sample_images.append({
                "scene_number": scene["scene_number"],
                "image_url": image_url,
            })
        
        logger.info("Video preview generated", user_id=current_user.id)
        
        return {
            "script": script,
            "sample_images": sample_images,
        }
        
    except Exception as e:
        logger.error("Video preview generation failed", error=str(e))
        raise AIServiceException("Failed to generate video preview")


@router.get("/niches")
async def get_niches():
    """Get available video niches."""
    return {
        "niches": [
            {"id": "animals", "name": "Animals & Pets", "icon": "🐾"},
            {"id": "tech", "name": "Technology", "icon": "💻"},
            {"id": "cooking", "name": "Cooking & Food", "icon": "🍳"},
            {"id": "motivation", "name": "Motivation", "icon": "💪"},
            {"id": "fitness", "name": "Fitness & Health", "icon": "🏋️"},
            {"id": "travel", "name": "Travel", "icon": "✈️"},
            {"id": "gaming", "name": "Gaming", "icon": "🎮"},
            {"id": "education", "name": "Education", "icon": "📚"},
            {"id": "comedy", "name": "Comedy", "icon": "😂"},
            {"id": "music", "name": "Music", "icon": "🎵"},
            {"id": "fashion", "name": "Fashion", "icon": "👗"},
            {"id": "business", "name": "Business", "icon": "💼"},
            {"id": "science", "name": "Science", "icon": "🔬"},
            {"id": "art", "name": "Art & Design", "icon": "🎨"},
            {"id": "nature", "name": "Nature", "icon": "🌿"},
        ]
    }


@router.get("/styles")
async def get_styles():
    """Get available video styles."""
    return {
        "styles": [
            {"id": "cartoon", "name": "Cartoon", "description": "Animated cartoon style"},
            {"id": "cinematic", "name": "Cinematic", "description": "Movie-like quality"},
            {"id": "realistic", "name": "Realistic", "description": "Photorealistic visuals"},
            {"id": "funny", "name": "Funny", "description": "Humorous and lighthearted"},
            {"id": "dramatic", "name": "Dramatic", "description": "Intense and emotional"},
            {"id": "minimal", "name": "Minimal", "description": "Clean and simple"},
        ]
    }


@router.get("/caption-styles")
async def get_caption_styles():
    """Get available caption styles."""
    return {
        "styles": [
            {"id": "modern", "name": "Modern", "font": "Montserrat", "animation": "slide-up"},
            {"id": "classic", "name": "Classic", "font": "Georgia", "animation": "fade-in"},
            {"id": "bold", "name": "Bold", "font": "Impact", "animation": "pop-in"},
            {"id": "minimal", "name": "Minimal", "font": "Inter", "animation": "typewriter"},
            {"id": "fun", "name": "Fun", "font": "Comic Sans", "animation": "bounce"},
        ]
    }


@router.get("/music-styles")
async def get_music_styles():
    """Get available background music styles."""
    return {
        "styles": [
            {"id": "upbeat", "name": "Upbeat", "description": "Energetic and positive"},
            {"id": "calm", "name": "Calm", "description": "Relaxing and peaceful"},
            {"id": "dramatic", "name": "Dramatic", "description": "Intense and emotional"},
            {"id": "funny", "name": "Funny", "description": "Playful and humorous"},
            {"id": "epic", "name": "Epic", "description": "Grand and inspiring"},
            {"id": "lofi", "name": "Lo-Fi", "description": "Chill and ambient"},
        ]
                                      }
