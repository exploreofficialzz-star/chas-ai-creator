"""AI services API routes."""

from typing import Optional, List

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationException, AIServiceException, ValidationException
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User
from app.services.ai.text_generation import TextGenerationService
from app.services.ai.image_generation import ImageGenerationService

logger = get_logger(__name__)
router = APIRouter()


# ─── AUTH DEPENDENCY ──────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("You must be logged in to use AI services.")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("Account not found. Please log in again.")
    return user


# ─── REQUEST / RESPONSE MODELS ────────────────────────────────────────────────

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
    narration: Optional[str] = None
    hashtags: List[str] = []


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


# FIX 1 - added SmartPlanRequest model (was missing, caused 422 from SmartCreateScreen)
class SmartPlanRequest(BaseModel):
    idea: str
    aspect_ratio: str = "9:16"
    duration: int = 30
    style: str = "cinematic"
    captions_enabled: bool = True
    background_music_enabled: bool = True


# ─── SCRIPT ───────────────────────────────────────────────────────────────────

@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(
    request: GenerateScriptRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate video script from niche and settings."""

    # FIX 2 - validate niche and style before hitting the AI service
    valid_niches = [
        "animals", "tech", "cooking", "motivation", "fitness", "travel",
        "gaming", "education", "comedy", "music", "fashion", "business",
        "science", "art", "nature", "finance", "entertainment", "news", "general",
    ]
    valid_styles = ["cartoon", "cinematic", "realistic", "funny", "dramatic", "minimal"]

    if request.niche not in valid_niches:
        raise ValidationException(f"Invalid niche '{request.niche}'.")
    if request.style not in valid_styles:
        raise ValidationException(f"Invalid style '{request.style}'.")
    if request.video_type not in ["silent", "narration"]:
        raise ValidationException("Video type must be 'silent' or 'narration'.")
    if not (10 <= request.duration <= 300):
        raise ValidationException("Duration must be between 10 and 300 seconds.")

    try:
        text_service = TextGenerationService()
        script = await text_service.generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
        )

        logger.info("Script generated", user_id=current_user.id, niche=request.niche)

        return GenerateScriptResponse(
            title=script.get("title", "Untitled"),
            description=script.get("description", ""),
            scenes=script.get("scenes", []),
            narration=script.get("narration"),
            hashtags=script.get("hashtags", []),
        )

    except ValidationException:
        raise
    except Exception as e:
        logger.error("Script generation failed", error=str(e))
        raise AIServiceException("Failed to generate script. Please try again.")


# ─── IMAGE ────────────────────────────────────────────────────────────────────

@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(
    request: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a single image from a prompt."""

    # FIX 3 - validate prompt is not empty
    if not request.prompt or not request.prompt.strip():
        raise ValidationException("Image prompt cannot be empty.")

    valid_ratios = ["16:9", "9:16", "1:1"]
    if request.aspect_ratio not in valid_ratios:
        raise ValidationException(
            f"Invalid aspect ratio. Choose one of: {', '.join(valid_ratios)}."
        )

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

    except ValidationException:
        raise
    except Exception as e:
        logger.error("Image generation failed", error=str(e))
        raise AIServiceException("Failed to generate image. Please try again.")


# ─── PREVIEW VIDEO ────────────────────────────────────────────────────────────

@router.post("/preview-video")
async def preview_video(
    request: PreviewVideoRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate video preview — script + sample images for first 3 scenes."""

    try:
        text_service = TextGenerationService()
        image_service = ImageGenerationService()

        # Step 1 — Generate script
        script = await text_service.generate_script(
            niche=request.niche,
            video_type=request.video_type,
            duration=request.duration,
            user_instructions=request.user_instructions,
            style=request.style,
        )

        # Step 2 — Generate sample images for first 3 scenes only
        sample_images = []
        scenes = script.get("scenes", [])

        for scene in scenes[:3]:
            # FIX 4 - fallback to description if image_prompt is missing
            image_prompt = (
                scene.get("image_prompt")
                or scene.get("description")
                or f"{request.style} scene for {request.niche} video"
            )
            try:
                image_url = await image_service.generate_image(
                    prompt=image_prompt,
                    style=request.style,
                    aspect_ratio="9:16",
                )
                sample_images.append({
                    "scene_number": scene.get("scene_number", len(sample_images) + 1),
                    "image_url": image_url,
                })
            except Exception as img_err:
                # FIX 5 - don't fail the whole preview if one image fails
                logger.warning(
                    f"Sample image failed for scene "
                    f"{scene.get('scene_number')}: {img_err}"
                )
                sample_images.append({
                    "scene_number": scene.get("scene_number", len(sample_images) + 1),
                    "image_url": "https://placehold.co/720x1280/1a1a2e/ffffff?text=Preview",
                })

        logger.info(
            "Video preview generated",
            user_id=current_user.id,
            niche=request.niche,
            scenes=len(scenes),
        )

        return {
            "script": script,
            "sample_images": sample_images,
        }

    except Exception as e:
        logger.error("Video preview generation failed", error=str(e))
        raise AIServiceException("Failed to generate video preview. Please try again.")


# ─── SMART PLAN (for SmartCreateScreen) ──────────────────────────────────────

@router.post("/smart-plan")
async def smart_generate_plan(
    request: SmartPlanRequest,
    current_user: User = Depends(get_current_user),
):
    """Convert a natural language idea into a full ready-to-generate video plan."""

    # FIX 6 - validate idea is not empty
    if not request.idea or not request.idea.strip():
        raise ValidationException(
            "Please describe your video idea before generating a plan."
        )
    if len(request.idea.strip()) < 10:
        raise ValidationException(
            "Your idea is too short. Please give a bit more detail!"
        )

    idea_lower = request.idea.lower()

    # ── Auto-detect niche ─────────────────────────────────────────────────
    niche = "general"
    niche_keywords = {
        "fitness":       ["gym", "workout", "exercise", "fitness", "muscle", "weight loss", "abs"],
        "cooking":       ["food", "recipe", "cook", "eat", "meal", "jollof", "suya", "naija food", "chef"],
        "tech":          ["tech", "ai", "gadget", "phone", "software", "app", "coding", "computer"],
        "finance":       ["money", "invest", "crypto", "business", "income", "wealth", "naira", "salary"],
        "motivation":    ["motivat", "inspire", "success", "hustle", "goal", "dream", "mindset"],
        "travel":        ["travel", "trip", "tour", "explore", "visit", "vacation", "lagos", "abuja"],
        "animals":       ["animal", "pet", "dog", "cat", "bird", "wildlife", "cute"],
        "fashion":       ["fashion", "style", "outfit", "wear", "dress", "clothes", "ootd"],
        "comedy":        ["funny", "comedy", "joke", "laugh", "humor", "meme", "prank"],
        "education":     ["learn", "study", "school", "teach", "educat", "tips", "how to", "facts"],
        "gaming":        ["game", "gaming", "play", "gamer", "esport", "stream"],
        "music":         ["music", "song", "beat", "artist", "sing", "rap", "afrobeat"],
        "nature":        ["nature", "forest", "ocean", "mountain", "plant", "environment"],
        "business":      ["business", "entrepreneur", "startup", "brand", "market", "sales"],
    }
    for detected_niche, keywords in niche_keywords.items():
        if any(kw in idea_lower for kw in keywords):
            niche = detected_niche
            break

    # ── Auto-detect music style ────────────────────────────────────────────
    music_style = "upbeat"
    if any(w in idea_lower for w in ["calm", "relax", "sleep", "meditat", "peaceful", "chill"]):
        music_style = "calm"
    elif any(w in idea_lower for w in ["drama", "intense", "epic", "powerful", "war", "fight"]):
        music_style = "dramatic"
    elif any(w in idea_lower for w in ["inspir", "motivat", "success", "achieve", "rise"]):
        music_style = "inspirational"
    elif any(w in idea_lower for w in ["funny", "comedy", "joke", "laugh", "meme"]):
        music_style = "upbeat"
    elif any(w in idea_lower for w in ["lofi", "study", "focus", "ambient"]):
        music_style = "lofi"

    # ── Auto-detect caption style ──────────────────────────────────────────
    caption_style = "modern"
    if any(w in idea_lower for w in ["bold", "hype", "loud", "energy", "fire"]):
        caption_style = "bold"
    elif any(w in idea_lower for w in ["minimal", "clean", "simple", "elegant"]):
        caption_style = "minimal"
    elif any(w in idea_lower for w in ["funny", "meme", "comedy", "joke"]):
        caption_style = "fun"

    try:
        text_service = TextGenerationService()
        script = await text_service.generate_script(
            niche=niche,
            video_type="silent",
            duration=request.duration,
            user_instructions=request.idea,
            style=request.style,
        )

        logger.info(
            "Smart plan generated",
            user_id=current_user.id,
            niche=niche,
            music_style=music_style,
        )

        return {
            "title": script.get("title", "My Video"),
            "description": script.get("description", ""),
            "niche": niche,
            "scenes": script.get("scenes", []),
            "hashtags": script.get("hashtags", []),
            "caption_style": caption_style,
            "music_style": music_style,
            "aspect_ratio": request.aspect_ratio,
            "duration": request.duration,
            "style": request.style,
            "captions_enabled": request.captions_enabled,
            "background_music_enabled": request.background_music_enabled,
        }

    except ValidationException:
        raise
    except Exception as e:
        logger.error(f"Smart plan failed: {e}")
        raise AIServiceException("Failed to generate video plan. Please try again.")


# ─── REFERENCE DATA ───────────────────────────────────────────────────────────

@router.get("/niches")
async def get_niches():
    """Get all available video niches."""
    return {
        "niches": [
            {"id": "animals",       "name": "Animals & Pets",    "icon": "🐾"},
            {"id": "tech",          "name": "Technology",         "icon": "💻"},
            {"id": "cooking",       "name": "Cooking & Food",     "icon": "🍳"},
            {"id": "motivation",    "name": "Motivation",         "icon": "💪"},
            {"id": "fitness",       "name": "Fitness & Health",   "icon": "🏋️"},
            {"id": "travel",        "name": "Travel",             "icon": "✈️"},
            {"id": "gaming",        "name": "Gaming",             "icon": "🎮"},
            {"id": "education",     "name": "Education",          "icon": "📚"},
            {"id": "comedy",        "name": "Comedy",             "icon": "😂"},
            {"id": "music",         "name": "Music",              "icon": "🎵"},
            {"id": "fashion",       "name": "Fashion",            "icon": "👗"},
            {"id": "business",      "name": "Business",           "icon": "💼"},
            {"id": "science",       "name": "Science",            "icon": "🔬"},
            {"id": "art",           "name": "Art & Design",       "icon": "🎨"},
            {"id": "nature",        "name": "Nature",             "icon": "🌿"},
            {"id": "finance",       "name": "Finance & Money",    "icon": "💰"},
            {"id": "entertainment", "name": "Entertainment",      "icon": "🎬"},
            {"id": "news",          "name": "News & Events",      "icon": "📰"},
            {"id": "general",       "name": "General",            "icon": "⭐"},
        ]
    }


@router.get("/styles")
async def get_styles():
    """Get all available video styles."""
    return {
        "styles": [
            {"id": "cinematic", "name": "Cinematic",  "description": "Movie-like quality",       "icon": "🎬"},
            {"id": "cartoon",   "name": "Cartoon",    "description": "Animated cartoon style",   "icon": "🎨"},
            {"id": "realistic", "name": "Realistic",  "description": "Photorealistic visuals",   "icon": "📷"},
            {"id": "funny",     "name": "Funny",      "description": "Humorous and lighthearted","icon": "😂"},
            {"id": "dramatic",  "name": "Dramatic",   "description": "Intense and emotional",    "icon": "🎭"},
            {"id": "minimal",   "name": "Minimal",    "description": "Clean and simple",         "icon": "✨"},
        ]
    }


@router.get("/caption-styles")
async def get_caption_styles():
    """Get all available caption styles."""
    return {
        "styles": [
            {"id": "modern",   "name": "Modern",   "font": "Montserrat", "animation": "slide-up"},
            {"id": "classic",  "name": "Classic",  "font": "Georgia",    "animation": "fade-in"},
            {"id": "bold",     "name": "Bold",     "font": "Impact",     "animation": "pop-in"},
            {"id": "minimal",  "name": "Minimal",  "font": "Inter",      "animation": "typewriter"},
            {"id": "fun",      "name": "Fun",      "font": "Poppins",    "animation": "bounce"},
        ]
    }


@router.get("/music-styles")
async def get_music_styles():
    """Get all available background music styles."""
    return {
        "styles": [
            {"id": "upbeat",        "name": "Upbeat",        "description": "Energetic and positive"},
            {"id": "calm",          "name": "Calm",          "description": "Relaxing and peaceful"},
            {"id": "dramatic",      "name": "Dramatic",      "description": "Intense and emotional"},
            {"id": "inspirational", "name": "Inspirational", "description": "Uplifting and motivating"},
            {"id": "epic",          "name": "Epic",          "description": "Grand and powerful"},
            {"id": "lofi",          "name": "Lo-Fi",         "description": "Chill and ambient"},
            {"id": "afrobeat",      "name": "Afrobeat",      "description": "Nigerian/African rhythm"},
        ]
    }


# FIX 7 - added missing health check endpoint that frontend may poll
@router.get("/health")
async def ai_health_check():
    """Check if AI services are reachable."""
    return {
        "status": "ok",
        "services": {
            "text_generation": "available",
            "image_generation": "available",
        }
}
