"""Text generation service using LLMs."""

import json
import re
from typing import List, Dict, Any, Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# FIX 1 - Qwen2-7B-Instruct is 410 Gone. These are tested working models
# on the free HuggingFace Inference API as of 2026
FALLBACK_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",        # Primary - fast, excellent quality
    "HuggingFaceH4/zephyr-7b-beta",              # Fallback 1 - great instruction following
    "tiiuae/falcon-7b-instruct",                  # Fallback 2 - reliable
    "google/flan-t5-large",                       # Fallback 3 - small but always available
]

# Niche-specific hashtag library
NICHE_HASHTAGS: Dict[str, List[str]] = {
    "general":       ["#viral", "#trending", "#fyp", "#foryou", "#content"],
    "animals":       ["#animals", "#pets", "#cute", "#animalsoftiktok", "#petlover", "#wildlife"],
    "tech":          ["#tech", "#technology", "#innovation", "#gadgets", "#ai", "#future"],
    "cooking":       ["#cooking", "#food", "#recipe", "#foodie", "#homemade", "#chef"],
    "motivation":    ["#motivation", "#inspiration", "#success", "#mindset", "#goals", "#hustle"],
    "fitness":       ["#fitness", "#workout", "#gym", "#health", "#exercise", "#bodybuilding"],
    "travel":        ["#travel", "#adventure", "#wanderlust", "#explore", "#vacation", "#tourism"],
    "gaming":        ["#gaming", "#gamer", "#videogames", "#gameplay", "#streamer", "#esports"],
    "education":     ["#education", "#learning", "#knowledge", "#study", "#facts", "#school"],
    "comedy":        ["#comedy", "#funny", "#humor", "#lol", "#meme", "#laugh"],
    "music":         ["#music", "#song", "#musician", "#artist", "#newmusic", "#hiphop"],
    "fashion":       ["#fashion", "#style", "#ootd", "#outfit", "#trendy", "#clothing"],
    "finance":       ["#finance", "#money", "#investing", "#wealth", "#business", "#entrepreneur"],
    "entertainment": ["#entertainment", "#celebrity", "#movies", "#tvshow", "#pop culture"],
    "news":          ["#news", "#currentevents", "#breaking", "#world", "#today"],
}

# Nigerian/African audience specific additions
NIGERIA_HASHTAGS = ["#naija", "#nigeria", "#africa", "#9ja", "#abuja", "#lagos"]

# Rich mock content library by niche
MOCK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "animals": {
        "titles": [
            "Adorable Animal Moments That Will Melt Your Heart 🐾",
            "Wild Animals Doing the Most Unexpected Things 🦁",
            "The Cutest Baby Animals You've Ever Seen 🐣",
        ],
        "scenes": [
            ("A fluffy golden retriever puppy playing in a sunny meadow", "Pure joy! 🐶"),
            ("A curious cat peeking from behind a colorful flower pot", "Caught you! 😸"),
            ("A baby elephant splashing water with its trunk", "Splash time! 🐘"),
            ("Penguins waddling on an icy landscape", "Squad goals 🐧"),
            ("A lion cub rolling in golden savanna grass", "King in training 👑"),
            ("A baby monkey swinging from a tree branch", "Hanging out 🐒"),
            ("Dolphins leaping through crystal ocean waves", "Freedom! 🐬"),
            ("A colorful parrot speaking into a tiny microphone", "Say it louder 🦜"),
        ],
    },
    "tech": {
        "titles": [
            "The Future of Technology is Here 🤖",
            "Top Tech Gadgets Changing the World in 2026 📱",
            "AI Is Doing WHAT Now?! 🧠",
        ],
        "scenes": [
            ("Futuristic holographic interface displaying data streams", "The future is NOW 🔮"),
            ("Robot arm precisely assembling electronics", "Precision like never before ⚙️"),
            ("Person in advanced VR headset exploring virtual world", "Step inside 🥽"),
            ("Smart home devices synced in a sleek modern apartment", "Your home, smarter 🏠"),
            ("AI chip under microscope with glowing circuits", "Brains of the future 💡"),
            ("Self-driving car navigating a busy city at night", "No hands needed 🚗"),
            ("Person charging phone wirelessly from across the room", "Zero cables needed ⚡"),
            ("Humanoid robot helping an elderly person walk", "Tech with heart 🤝"),
        ],
    },
    "cooking": {
        "titles": [
            "Quick & Delicious Nigerian Recipe You Need to Try 🍲",
            "5-Minute Meals That Taste Like Hours of Cooking ⏱️",
            "Street Food Magic: Recipes from Lagos 🌶️",
        ],
        "scenes": [
            ("Fresh ingredients beautifully arranged on a wooden board", "Fresh is best 🥦"),
            ("Chef's hands chopping colorful vegetables", "Chop it up! 🔪"),
            ("Steam rising from a sizzling pan with jollof rice", "The aroma! 😋"),
            ("Perfectly plated dish garnished with herbs", "Eat with your eyes first 👀"),
            ("Pouring rich palm oil stew over white rice", "Nigerian classic 🍛"),
            ("Crispy suya being sliced on a wooden board", "Suya time! 🔥"),
            ("Freshly fried puff puff golden and fluffy", "Snack time 🟡"),
            ("Cold zobo drink poured into a glass with ice", "Refreshing! 🍹"),
        ],
    },
    "motivation": {
        "titles": [
            "Believe in Yourself — Anything Is Possible 💪",
            "From Zero to Hero: Your Comeback Story Starts Now 🚀",
            "Stop Waiting, Start Building Your Dreams Today 🔥",
        ],
        "scenes": [
            ("Person standing on mountain peak at sunrise, arms wide open", "You made it 🌅"),
            ("Hands writing bold goals in a leather journal", "Write it down ✍️"),
            ("Athlete sprinting on track in the rain, never stopping", "Push harder 🏃"),
            ("Entrepreneur celebrating a big win in their office", "Success is yours 🏆"),
            ("Student studying late under a lamp, determined face", "Grind season 📚"),
            ("Young African professional in a sharp suit, confident", "Dress for success 👔"),
            ("Person smashing a board with their bare hands", "Break your limits 💥"),
            ("Sunrise over Lagos skyline, full of possibility", "New day, new chance 🌄"),
        ],
    },
    "fitness": {
        "titles": [
            "Transform Your Body in 30 Days With This Workout 💪",
            "Home Workout Routine That Actually Works 🏠",
            "No Gym? No Problem — Build Muscle Anywhere 🔥",
        ],
        "scenes": [
            ("Person doing explosive push-ups at sunrise outdoors", "Morning grind 🌅"),
            ("Athlete performing clean pull-ups on outdoor bar", "Level up 💪"),
            ("Person doing high knees in a home living room", "No gym needed 🏠"),
            ("Trainer demonstrating perfect squat form", "Form is everything 🎯"),
            ("Person drinking protein shake post-workout", "Fuel your gains 🥤"),
            ("Before and after split screen of body transformation", "The results speak 📊"),
            ("Group fitness class energy, everyone sweating", "Team work 👥"),
            ("Person meditating after intense workout session", "Recovery matters 🧘"),
        ],
    },
    "travel": {
        "titles": [
            "Hidden Gems in Nigeria You've Never Seen 🇳🇬",
            "Top African Destinations to Visit in 2026 ✈️",
            "Budget Travel Hacks That Actually Work 💰",
        ],
        "scenes": [
            ("Aerial view of Erin Ijesha waterfall, Nigeria", "Nature's masterpiece 🌊"),
            ("Colorful Lagos market filled with vibrant textiles", "Culture overload 🎨"),
            ("Sunset over Lekki beach with golden reflections", "Golden hour 🌅"),
            ("Traditional Benin bronze sculptures in museum", "Rich heritage 🏛️"),
            ("Traveler hiking through Obudu mountain range", "Adventure awaits ⛰️"),
            ("Street food scene in Abuja Night Market", "Eat like a local 🍢"),
            ("Luxury resort pool overlooking the ocean", "Living the life 🏖️"),
            ("Plane window view above African clouds at sunset", "Up and away ✈️"),
        ],
    },
    "finance": {
        "titles": [
            "How to Make Money Work for You in Nigeria 💰",
            "Investment Strategies Every Nigerian Should Know 📈",
            "From Salary to Wealth: The Nigerian Blueprint 🏦",
        ],
        "scenes": [
            ("Stack of naira notes next to investment charts", "Money moves 💵"),
            ("Person using banking app on phone confidently", "Digital finance 📱"),
            ("Real estate properties in an upscale neighborhood", "Property wins 🏘️"),
            ("Stock market graph trending sharply upward", "Watch it grow 📈"),
            ("Young entrepreneur receiving payment notification", "Ding! Money in 💸"),
            ("Person opening a savings account at a bank", "Start saving today 🏦"),
            ("Laptop showing crypto portfolio growth", "Future of finance 🔐"),
            ("Successful Nigerian family in their own home", "The dream 🏠"),
        ],
    },
}


class TextGenerationService:
    """Service for generating video scripts and text content."""

    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        # FIX 2 - hardcode base URL, don't rely on stale settings value
        self.api_base = "https://api-inference.huggingface.co/models"
        self.scene_duration = 3  # seconds per scene

    async def generate_script(
        self,
        niche: str,
        video_type: str = "silent",
        duration: int = 30,
        user_instructions: Optional[str] = None,
        style: str = "cinematic",
    ) -> Dict[str, Any]:
        """Generate video script with scenes and hashtags."""

        num_scenes = max(3, duration // self.scene_duration)
        prompt = self._build_script_prompt(
            niche=niche,
            video_type=video_type,
            num_scenes=num_scenes,
            user_instructions=user_instructions,
            style=style,
        )

        script_text = None

        # FIX 3 - try each model in order until one succeeds
        if self.api_key:
            for model in FALLBACK_MODELS:
                try:
                    logger.info(f"Trying text model: {model}")
                    script_text = await self._call_huggingface_api(prompt, model)
                    if script_text and len(script_text.strip()) > 50:
                        logger.info(f"Script generated with model: {model}")
                        break
                except Exception as e:
                    err = str(e)
                    if any(code in err for code in ["410", "404", "503", "loading"]):
                        logger.warning(f"Model {model} unavailable: {err[:80]}, trying next...")
                        continue
                    else:
                        logger.error(f"Text generation error with {model}: {err}")
                        continue

        # FIX 4 - if all API models fail, use rich mock templates (not blank fallback)
        if not script_text:
            logger.warning("All HuggingFace text models failed — using rich mock template")
            return self._generate_rich_mock_script(niche, num_scenes, style, user_instructions)

        # Parse and enrich the script
        script = self._parse_script(script_text, num_scenes)

        # FIX 5 - validate scenes have required fields, fill gaps if needed
        script = self._validate_and_fill_script(script, niche, num_scenes, style)

        # Generate narration if needed
        if video_type == "narration":
            script["narration"] = await self._generate_narration(script)

        # Always generate hashtags
        script["hashtags"] = self._generate_hashtags(niche, script.get("title", ""))

        logger.info(f"Script complete: '{script.get('title')}' with {len(script['scenes'])} scenes")
        return script

    def _build_script_prompt(
        self,
        niche: str,
        video_type: str,
        num_scenes: int,
        user_instructions: Optional[str],
        style: str,
    ) -> str:
        """Build a tight, clear prompt that LLMs reliably follow."""

        narration_note = (
            "Each scene must include a 'narration' field with voiceover text."
            if video_type == "narration" else ""
        )
        instructions_note = (
            f"Creator's special instructions: {user_instructions}"
            if user_instructions else ""
        )

        return f"""You are a professional short-form video scriptwriter.
Create a {style}-style video script about {niche} content for a Nigerian/African audience.

Requirements:
- Exactly {num_scenes} scenes
- Each scene should be visual, engaging, and shareable
- Captions must be short (max 8 words), punchy, with emojis
- Image prompts must be detailed and specific for AI image generation
{narration_note}
{instructions_note}

Respond ONLY with valid JSON, no extra text, no markdown:
{{
  "title": "Catchy video title with emoji",
  "description": "One sentence description",
  "scenes": [
    {{
      "scene_number": 1,
      "description": "What happens in this scene visually",
      "caption": "Short punchy caption with emoji",
      "image_prompt": "Detailed prompt for AI image generation, {style} style, high quality, 4k"
    }}
  ]
}}"""

    async def _call_huggingface_api(self, prompt: str, model: str) -> str:
        """Call HuggingFace Inference API for a specific model."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # FIX 6 - different models need different payload formats
        if "flan-t5" in model:
            # Encoder-decoder models use simple inputs
            payload = {
                "inputs": prompt[:512],  # T5 has shorter context
                "parameters": {"max_new_tokens": 512},
            }
        else:
            # Decoder-only instruct models
            payload = {
                "inputs": f"[INST] {prompt} [/INST]",
                "parameters": {
                    "max_new_tokens": 1500,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "return_full_text": False,
                    "stop": ["</s>", "[INST]"],
                },
                "options": {
                    "wait_for_model": False,
                    "use_cache": True,
                },
            }

        model_url = f"{self.api_base}/{model}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                model_url,
                headers=headers,
                json=payload,
                timeout=60.0,
            )

            if response.status_code == 503:
                raise Exception("503 Model is loading")

            response.raise_for_status()
            result = response.json()

            # FIX 7 - handle both list and dict response formats
            if isinstance(result, list) and result:
                return result[0].get("generated_text", "")
            elif isinstance(result, dict):
                if "error" in result:
                    raise Exception(f"API error: {result['error']}")
                return result.get("generated_text", str(result))
            return str(result)

    def _parse_script(self, text: str, expected_scenes: int) -> Dict[str, Any]:
        """Parse LLM output into structured script dict."""

        if not text:
            return {}

        # FIX 8 - try multiple JSON extraction strategies
        # Strategy 1: clean JSON block
        try:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Strategy 2: fix common LLM JSON mistakes (trailing commas, single quotes)
        try:
            cleaned = re.sub(r',\s*}', '}', text)
            cleaned = re.sub(r',\s*]', ']', cleaned)
            cleaned = cleaned.replace("'", '"')
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, Exception):
            pass

        # Strategy 3: line-by-line fallback parser
        return self._fallback_parse_script(text, expected_scenes)

    def _fallback_parse_script(self, text: str, num_scenes: int) -> Dict[str, Any]:
        """Best-effort line parser when JSON extraction fails."""

        lines = text.strip().split("\n")
        script: Dict[str, Any] = {
            "title": "Generated Video",
            "description": "AI-generated content",
            "scenes": [],
        }

        current_scene: Optional[Dict] = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if low.startswith("title:"):
                script["title"] = line.split(":", 1)[1].strip()
            elif low.startswith("description:"):
                script["description"] = line.split(":", 1)[1].strip()
            elif re.match(r'^scene\s*\d+', low) and ":" in line:
                if current_scene:
                    script["scenes"].append(current_scene)
                current_scene = {
                    "scene_number": len(script["scenes"]) + 1,
                    "description": line.split(":", 1)[1].strip(),
                    "caption": "",
                    "image_prompt": "",
                }
            elif current_scene:
                if low.startswith("caption:"):
                    current_scene["caption"] = line.split(":", 1)[1].strip()
                elif low.startswith("image prompt:") or low.startswith("prompt:"):
                    current_scene["image_prompt"] = line.split(":", 1)[1].strip()
                elif not current_scene["caption"]:
                    current_scene["caption"] = line
                else:
                    current_scene["image_prompt"] += " " + line

        if current_scene:
            script["scenes"].append(current_scene)

        return script

    def _validate_and_fill_script(
        self,
        script: Dict[str, Any],
        niche: str,
        num_scenes: int,
        style: str,
    ) -> Dict[str, Any]:
        """FIX 9 - Ensure every scene has all required fields, fill gaps with smart defaults."""

        if not script.get("title"):
            script["title"] = f"Amazing {niche.title()} Content 🔥"
        if not script.get("description"):
            script["description"] = f"Discover amazing {niche} moments"
        if not script.get("scenes"):
            script["scenes"] = []

        # Fill missing scenes
        while len(script["scenes"]) < num_scenes:
            i = len(script["scenes"]) + 1
            script["scenes"].append({
                "scene_number": i,
                "description": f"Engaging {niche} scene {i}",
                "caption": f"Watch this! 🔥",
                "image_prompt": (
                    f"High quality {style} image for {niche} content, scene {i}, "
                    f"professional, detailed, 4k"
                ),
            })

        # Fix each scene's fields
        for i, scene in enumerate(script["scenes"]):
            scene["scene_number"] = i + 1
            if not scene.get("description"):
                scene["description"] = f"Scene {i + 1}: {niche} moment"
            if not scene.get("caption"):
                scene["caption"] = f"Amazing! 🎯"
            if not scene.get("image_prompt"):
                scene["image_prompt"] = (
                    f"{style} style, {scene['description']}, "
                    f"high quality, 4k, detailed"
                )

        # Trim to exact scene count
        script["scenes"] = script["scenes"][:num_scenes]

        return script

    def _generate_rich_mock_script(
        self,
        niche: str,
        num_scenes: int,
        style: str,
        user_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """FIX 10 - Rich mock script with real content per niche, not blank placeholders."""

        template = MOCK_TEMPLATES.get(niche.lower(), MOCK_TEMPLATES["motivation"])

        title = template["titles"][0]
        if user_instructions:
            title = f"{title} — {user_instructions[:30]}"

        scene_templates = template["scenes"]
        scenes = []
        for i in range(num_scenes):
            tpl = scene_templates[i % len(scene_templates)]
            desc, caption = tpl
            scenes.append({
                "scene_number": i + 1,
                "description": desc,
                "caption": caption,
                "image_prompt": (
                    f"{style} style, {desc}, Nigerian/African aesthetic, "
                    f"vibrant, high quality, 4k, detailed lighting"
                ),
            })

        return {
            "title": title,
            "description": f"Engaging {niche} content for the African audience",
            "scenes": scenes,
            "hashtags": self._generate_hashtags(niche, title),
        }

    async def _generate_narration(self, script: Dict[str, Any]) -> str:
        """Generate full narration from scene captions."""
        scenes = script.get("scenes", [])
        parts = []
        for scene in scenes:
            caption = scene.get("caption", "")
            desc = scene.get("description", "")
            # FIX 11 - use description for richer narration, not just caption
            if desc:
                # Strip emojis for speech
                clean = re.sub(r'[^\w\s,!?.]', '', desc)
                parts.append(clean.strip())
        return ". ".join(parts) + "."

    def _generate_hashtags(self, niche: str, title: str) -> List[str]:
        """Generate relevant hashtags including Nigerian audience tags."""

        base_tags = NICHE_HASHTAGS.get(niche.lower(), NICHE_HASHTAGS["general"]).copy()

        # FIX 12 - add Nigeria hashtags for Nigerian audience
        base_tags.extend(NIGERIA_HASHTAGS[:2])

        # Add title-based hashtags
        title_words = re.sub(r'[^\w\s]', '', title.lower()).split()
        for word in title_words:
            if len(word) > 4 and f"#{word}" not in base_tags:
                base_tags.append(f"#{word}")
                if len(base_tags) >= 12:
                    break

        return base_tags[:12]

    def _generate_fallback_script(self, niche: str, num_scenes: int) -> Dict[str, Any]:
        """Last-resort fallback — delegates to rich mock."""
        return self._generate_rich_mock_script(niche, num_scenes, "cinematic")
