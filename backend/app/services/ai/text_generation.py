"""
Text generation service using LLMs.
FILE: app/services/ai/text_generation.py

FIXES:
1. generate_script() was missing aspect_ratio, target_platforms, voice_style
   params — video_generation.py task passes all three, causing TypeError.

2. MOCK_TEMPLATES was missing niches: gaming, education, comedy, music,
   fashion, entertainment, news — these would fall through to "motivation"
   template silently.

3. _generate_narration() — was stripping ALL non-word chars including
   spaces, making narration run-on. Fixed regex to preserve spaces.

4. smart_generate_plan() added — this is what ai_services.py calls for
   the /smart-plan endpoint used by SmartCreateScreen.

5. platform_tips added to smart plan — frontend's Platforms tab was
   always empty because the API never returned platform_tips.

6. caption field added per-scene for smart plan — frontend scene card
   shows caption in italic below description.
"""

import json
import re
from typing import List, Dict, Any, Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

FALLBACK_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "HuggingFaceH4/zephyr-7b-beta",
    "tiiuae/falcon-7b-instruct",
    "google/flan-t5-large",
]

NICHE_HASHTAGS: Dict[str, List[str]] = {
    "general":       ["#viral", "#trending", "#fyp", "#foryou", "#content"],
    "animals":       ["#animals", "#pets", "#cute", "#animalsoftiktok", "#petlover", "#wildlife"],
    "tech":          ["#tech", "#technology", "#innovation", "#gadgets", "#ai", "#future"],
    "cooking":       ["#cooking", "#food", "#recipe", "#foodie", "#homemade", "#chef"],
    "motivation":    ["#motivation", "#inspiration", "#success", "#mindset", "#goals", "#hustle"],
    "fitness":       ["#fitness", "#workout", "#gym", "#health", "#exercise", "#bodybuilding"],
    "travel":        ["#travel", "#adventure", "#wanderlust", "#explore", "#vacation", "#tourism"],
    "gaming":        ["#gaming", "#gamer", "#videogames", "#gameplay", "#streamer", "#esports"],
    "education":     ["#education", "#learning", "#knowledge", "#study", "#facts", "#didyouknow"],
    "comedy":        ["#comedy", "#funny", "#humor", "#lol", "#meme", "#laugh"],
    "music":         ["#music", "#song", "#musician", "#artist", "#newmusic", "#afrobeats"],
    "fashion":       ["#fashion", "#style", "#ootd", "#outfit", "#trendy", "#africanfashion"],
    "finance":       ["#finance", "#money", "#investing", "#wealth", "#business", "#entrepreneur"],
    "entertainment": ["#entertainment", "#celebrity", "#movies", "#tvshow", "#nollywood"],
    "news":          ["#news", "#currentevents", "#breaking", "#world", "#naijanews"],
}

NIGERIA_HASHTAGS = ["#naija", "#nigeria", "#africa", "#9ja", "#abuja", "#lagos"]

PLATFORM_TIPS: Dict[str, Dict[str, str]] = {
    "tiktok":    {"tip": "Use trending audio and post between 7–9 PM WAT for max reach.",    "best_time": "7–9 PM WAT"},
    "youtube":   {"tip": "Add chapters and a strong hook in the first 3 seconds.",           "best_time": "12–3 PM WAT"},
    "instagram": {"tip": "Reels under 30s get boosted. Use 3–5 niche hashtags in caption.",  "best_time": "11 AM–1 PM WAT"},
    "facebook":  {"tip": "Native uploads get 3× more reach than shared links. Post Tue–Thu.", "best_time": "1–3 PM WAT"},
    "twitter":   {"tip": "Thread the video with a strong opening tweet to drive clicks.",     "best_time": "8–10 AM WAT"},
    "linkedin":  {"tip": "Start with a bold insight or stat. Professional tone works best.",  "best_time": "Tue 8–10 AM WAT"},
}

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
            ("Robot arm precisely assembling electronics in a lab", "Precision like never before ⚙️"),
            ("Person in advanced VR headset exploring virtual world", "Step inside 🥽"),
            ("Smart home devices synced in a sleek modern apartment", "Your home, smarter 🏠"),
            ("AI chip under microscope with glowing circuits", "Brains of the future 💡"),
            ("Self-driving car navigating a busy city at night", "No hands needed 🚗"),
            ("Person charging phone wirelessly from across a room", "Zero cables ⚡"),
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
            ("Chef's hands chopping colorful vegetables rapidly", "Chop it up! 🔪"),
            ("Steam rising from a sizzling pan with jollof rice", "The aroma! 😋"),
            ("Perfectly plated dish garnished with fresh herbs", "Eat with your eyes first 👀"),
            ("Pouring rich palm oil stew over white rice", "Nigerian classic 🍛"),
            ("Crispy suya being sliced on a wooden board over coals", "Suya time! 🔥"),
            ("Freshly fried puff puff golden and fluffy on a tray", "Snack time 🟡"),
            ("Cold zobo drink poured into a glass with ice cubes", "Refreshing! 🍹"),
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
            ("Athlete performing clean pull-ups on an outdoor bar", "Level up 💪"),
            ("Person doing high knees in a home living room", "No gym needed 🏠"),
            ("Trainer demonstrating perfect squat form in a gym", "Form is everything 🎯"),
            ("Person drinking protein shake post-workout outside", "Fuel your gains 🥤"),
            ("Before and after split screen of body transformation", "The results speak 📊"),
            ("Group fitness class with everyone sweating together", "Team work 👥"),
            ("Person meditating after an intense workout session", "Recovery matters 🧘"),
        ],
    },
    "travel": {
        "titles": [
            "Hidden Gems in Nigeria You've Never Seen 🇳🇬",
            "Top African Destinations to Visit in 2026 ✈️",
            "Budget Travel Hacks That Actually Work 💰",
        ],
        "scenes": [
            ("Aerial view of Erin Ijesha waterfall cascading through forest", "Nature's masterpiece 🌊"),
            ("Colorful Lagos market filled with vibrant textiles and people", "Culture overload 🎨"),
            ("Sunset over Lekki beach with golden reflections on water", "Golden hour 🌅"),
            ("Traditional Benin bronze sculptures displayed in a museum", "Rich heritage 🏛️"),
            ("Traveler hiking through Obudu mountain range at sunrise", "Adventure awaits ⛰️"),
            ("Busy street food scene in Abuja Night Market with lights", "Eat like a local 🍢"),
            ("Luxury resort pool overlooking a pristine ocean view", "Living the life 🏖️"),
            ("Plane window view above African clouds at golden sunset", "Up and away ✈️"),
        ],
    },
    "finance": {
        "titles": [
            "How to Make Money Work for You in Nigeria 💰",
            "Investment Strategies Every Nigerian Should Know 📈",
            "From Salary to Wealth: The Nigerian Blueprint 🏦",
        ],
        "scenes": [
            ("Stack of naira notes arranged next to investment charts", "Money moves 💵"),
            ("Person confidently using a mobile banking app", "Digital finance 📱"),
            ("Real estate properties in an upscale Nigerian neighborhood", "Property wins 🏘️"),
            ("Stock market graph trending sharply upward with green bars", "Watch it grow 📈"),
            ("Young entrepreneur receiving payment notification on phone", "Ding! Money in 💸"),
            ("Person opening a savings account at a modern bank branch", "Start saving today 🏦"),
            ("Laptop showing a crypto or investment portfolio in profit", "Future of finance 🔐"),
            ("Successful Nigerian family standing proudly in their home", "The dream 🏠"),
        ],
    },
    # FIX 2 — added missing niches
    "gaming": {
        "titles": [
            "Gaming Moments That Broke the Internet 🎮",
            "Top 5 Games Every African Gamer Must Play in 2026 🕹️",
            "When the Game Gets TOO Real 😱",
        ],
        "scenes": [
            ("Gamer's hands on controller with intense focus, screen glow", "In the zone 🎮"),
            ("Huge esports arena packed with screaming fans in Africa", "The crowd goes wild 🏟️"),
            ("Epic in-game explosion with a player celebrating wildly", "Get rekt! 💥"),
            ("Streamer laughing hard at an unexpected game moment", "LOL moment 😂"),
            ("Top player's leaderboard showing rank #1 globally", "World's best 🥇"),
            ("Split screen showing beginner vs pro playing same level", "The glow up 📈"),
            ("Unboxing a brand new gaming setup in a dark room", "Setup reveal 📦"),
            ("Final boss defeated with epic slow-motion cutscene", "Victory! 🏆"),
        ],
    },
    "education": {
        "titles": [
            "Mind-Blowing Facts You Won't Believe Are True 🤯",
            "Learn This Skill in 60 Seconds and Change Your Life 📚",
            "Things School Never Taught You But Should Have 🎓",
        ],
        "scenes": [
            ("Animated brain lighting up with colorful knowledge sparks", "Knowledge unlocked 🧠"),
            ("Student's eureka moment, light bulb above their head", "Aha moment! 💡"),
            ("Open book with vibrant illustrations flying off the pages", "Words come alive 📖"),
            ("Chalkboard filling up with equations and diagrams rapidly", "Big brain time 🔢"),
            ("Person confidently presenting a project to an audience", "Speak your truth 🎤"),
            ("African teacher and excited students in a bright classroom", "Education wins 👩‍🏫"),
            ("Split screen: person who studied vs person who didn't", "Study or regret 📊"),
            ("Graduation cap tossed in air with confetti celebration", "You made it 🎓"),
        ],
    },
    "comedy": {
        "titles": [
            "When Life in Nigeria Gets Too Funny 😂",
            "Relatable African Moments That Hit Different 💀",
            "Nigerian Mum Energy We All Know Too Well 👀",
        ],
        "scenes": [
            ("Person doing an exaggerated double-take at shocking news", "Did they really?! 😭"),
            ("Classic Nigerian mum face when you come home late", "You're finished 😤"),
            ("Person trying to explain a mistake with wild hand gestures", "It wasn't me! 🙈"),
            ("Overly dressed person showing up to a casual hangout", "Extra level 100 💃"),
            ("Phone battery dying at the most dramatic possible moment", "WHY NOW?! 😩"),
            ("Person dancing alone thinking no one is watching them", "Caught in 4K 📷"),
            ("Queue of people rushing as NEPA restores power suddenly", "Light don come! ⚡"),
            ("Friends arguing about who ate the last piece of food", "Who touched my food 😡"),
        ],
    },
    "music": {
        "titles": [
            "Afrobeats Songs Breaking the Internet Right Now 🎵",
            "Nigerian Artists Who Are Taking Over the World 🌍",
            "When the Beat Drops Just Right 🔥",
        ],
        "scenes": [
            ("Concert crowd dancing to afrobeats under colorful stage lights", "Feel the vibe 🎶"),
            ("Artist recording in a professional Lagos music studio", "In the booth 🎙️"),
            ("Vinyl record spinning with vibrant music wave visualizer", "Good music hits different 🎵"),
            ("Street dancer freestyling to afrobeats in a Lagos market", "Lagos moves 💃"),
            ("Split screen comparing old vs new Nigerian music eras", "The evolution 📈"),
            ("Musician at a piano composing a soulful melody alone", "The creation 🎹"),
            ("Fans singing every word at a live concert passionately", "We know all the words 🎤"),
            ("Album artwork reveal with dramatic lighting and energy", "New music incoming 🔊"),
        ],
    },
    "fashion": {
        "titles": [
            "African Fashion That's Taking Over the World 👗",
            "How to Slay on a Budget Like a Nigerian 💅",
            "Ankara Outfit Ideas You Need This Season 🧵",
        ],
        "scenes": [
            ("Model in stunning Ankara outfit walking confidently on runway", "Slay nation 👑"),
            ("Close-up of intricate handmade African beadwork jewelry", "Craftsmanship 💎"),
            ("Fashion designer sketching bold new collection in Lagos", "Creating magic ✏️"),
            ("Street style photo shoot in colorful Lekki neighborhood", "Lagos streets 📸"),
            ("Before and after styling transformation with local fabric", "The glow up ✨"),
            ("Hairstylist finishing an elaborate braided updo", "Crown complete 💆"),
            ("Flat lay of colorful African print accessories and fabric", "The details 🎨"),
            ("Group of friends dressed in matching Ankara outfits laughing", "Aso-ebi goals 👯"),
        ],
    },
    "entertainment": {
        "titles": [
            "Nollywood Scenes That Hit Completely Different 🎬",
            "Nigerian Celebrities Living Their Best Life 🌟",
            "African Pop Culture Moments Nobody Saw Coming 👀",
        ],
        "scenes": [
            ("Nollywood movie premiere with red carpet and flashbulbs", "Lights, camera! 🎬"),
            ("Nigerian celebrity surprising fans with generous gift", "King/Queen behavior 👑"),
            ("Behind the scenes of a major African music video shoot", "Making magic 🎥"),
            ("Award show moment with emotional winner speech", "They deserve it 🏆"),
            ("Iconic movie line being reenacted with hilarious result", "Classic moment 😂"),
            ("African content creator filming viral video in kitchen", "Going viral 📱"),
            ("Sold-out concert venue with massive crowd energy", "Epic show 🎉"),
            ("Two celebrities meeting unexpectedly with surprised reaction", "The crossover 🤝"),
        ],
    },
    "news": {
        "titles": [
            "Breaking News That Every Nigerian Needs to Know Today 📰",
            "Top 5 Stories Shaping Africa Right Now 🌍",
            "What's Really Going On in Nigeria This Week 🇳🇬",
        ],
        "scenes": [
            ("News anchor at desk with BREAKING NEWS banner below", "Breaking now 📺"),
            ("Aerial view of an event or development in a Nigerian city", "On the ground 🛰️"),
            ("Journalist interviewing key figure on location outdoors", "Getting answers 🎙️"),
            ("Social media feed blowing up with trending hashtag", "Twitter is talking 🐦"),
            ("Graph or infographic showing key statistics visually", "The numbers 📊"),
            ("Citizens reacting to major announcement on the street", "People's voice 🗣️"),
            ("Government building or institution relevant to the story", "Official response 🏛️"),
            ("Split screen showing what was promised vs what happened", "Accountability 📋"),
        ],
    },
}


class TextGenerationService:
    """Service for generating video scripts and text content."""

    def __init__(self):
        self.api_key  = settings.HUGGINGFACE_API_KEY
        self.api_base = "https://api-inference.huggingface.co/models"
        self.scene_duration = 3  # seconds per scene

    # ─── MAIN SCRIPT GENERATION ───────────────────────────────────────────────

    async def generate_script(
        self,
        niche: str,
        video_type: str = "silent",
        duration: int = 30,
        user_instructions: Optional[str] = None,
        style: str = "cinematic",
        # FIX 1 — new params that video_generation.py task passes
        aspect_ratio: str = "9:16",
        target_platforms: Optional[List[str]] = None,
        voice_style: str = "professional",
    ) -> Dict[str, Any]:
        """Generate full video script with scenes, hashtags, and narration."""

        if target_platforms is None:
            target_platforms = ["tiktok"]

        num_scenes = max(3, duration // self.scene_duration)

        prompt = self._build_script_prompt(
            niche=niche,
            video_type=video_type,
            num_scenes=num_scenes,
            user_instructions=user_instructions,
            style=style,
            target_platforms=target_platforms,
            voice_style=voice_style,
        )

        script_text = None

        if self.api_key:
            for model in FALLBACK_MODELS:
                try:
                    logger.info(f"Trying text model: {model}")
                    script_text = await self._call_huggingface_api(prompt, model)
                    if script_text and len(script_text.strip()) > 50:
                        logger.info(f"Script generated with: {model}")
                        break
                except Exception as e:
                    err = str(e)
                    if any(c in err for c in ["410", "404", "503", "loading"]):
                        logger.warning(f"Model {model} unavailable: {err[:80]}")
                        continue
                    logger.error(f"Text gen error {model}: {err}")

        if not script_text:
            logger.warning("All HF text models failed — using rich mock template")
            return self._generate_rich_mock_script(
                niche, num_scenes, style, user_instructions, target_platforms
            )

        script = self._parse_script(script_text, num_scenes)
        script = self._validate_and_fill_script(script, niche, num_scenes, style)

        if video_type in ("narration", "sound_sync"):
            script["narration"] = self._build_narration(script, voice_style)

        script["hashtags"]  = self._generate_hashtags(niche, script.get("title", ""))
        script["seo_tags"]  = self._generate_seo_tags(niche, target_platforms)
        script["music_style"] = self._pick_music_style(niche, style)

        logger.info(
            f"Script complete: '{script.get('title')}' "
            f"| {len(script['scenes'])} scenes | platforms={target_platforms}"
        )
        return script

    # ─── SMART PLAN (used by /api/v1/ai/smart-plan endpoint) ─────────────────

    async def smart_generate_plan(
        self,
        idea: str,
        aspect_ratio: str = "9:16",
        duration: int = 30,
        style: str = "cinematic",
        captions_enabled: bool = True,
        background_music_enabled: bool = True,
        audio_mode: str = "narration",
        voice_style: str = "professional",
        target_platforms: Optional[List[str]] = None,
        character_consistency: bool = False,
        uploaded_image_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate a full SmartCreate plan with scenes, copy, hashtags,
        SEO tags, and per-platform tips.
        Called by ai_services.py /smart-plan endpoint.
        """
        if target_platforms is None:
            target_platforms = ["tiktok"]

        # Detect niche from idea text
        niche = self._detect_niche(idea)
        num_scenes = max(3, duration // self.scene_duration)

        # Generate the base script using user's idea as instructions
        script = await self.generate_script(
            niche=niche,
            video_type=audio_mode,
            duration=duration,
            user_instructions=idea,
            style=style,
            aspect_ratio=aspect_ratio,
            target_platforms=target_platforms,
            voice_style=voice_style,
        )

        # FIX 5 — build platform_tips (was missing → Platforms tab always empty)
        platform_tips = {
            p: PLATFORM_TIPS.get(p, {"tip": "Post consistently for best results.", "best_time": "Peak hours"})
            for p in target_platforms
        }

        # Caption for the post (separate from in-video captions)
        post_caption = (
            f"{script.get('description', '')}\n\n"
            + " ".join(script.get("hashtags", [])[:8])
        )

        return {
            "title":         script.get("title"),
            "description":   script.get("description"),
            "niche":         niche,
            "caption":       post_caption,
            "caption_style": self._pick_caption_style(style),
            "music_style":   script.get("music_style", "upbeat"),
            # FIX 6 — scenes include caption field for frontend scene cards
            "scenes":        script.get("scenes", []),
            "hashtags":      script.get("hashtags", []),
            "seo_tags":      script.get("seo_tags", []),
            "narration":     script.get("narration"),
            # FIX 5 — platform_tips now populated
            "platform_tips": platform_tips,
            "aspect_ratio":  aspect_ratio,
            "estimated_duration": duration,
        }

    # ─── PROMPT BUILDER ───────────────────────────────────────────────────────

    def _build_script_prompt(
        self,
        niche: str,
        video_type: str,
        num_scenes: int,
        user_instructions: Optional[str],
        style: str,
        target_platforms: List[str],
        voice_style: str,
    ) -> str:

        platforms_str = ", ".join(target_platforms) if target_platforms else "TikTok"
        narration_note = (
            f'Each scene must include "narration" field with {voice_style} voice text.'
            if video_type in ("narration", "sound_sync") else ""
        )
        instructions_note = (
            f"Creator's special instructions: {user_instructions}"
            if user_instructions else ""
        )

        return f"""You are a professional short-form video scriptwriter for African audiences.
Create a {style}-style video about: {niche}
Target platforms: {platforms_str}
{instructions_note}

Rules:
- Exactly {num_scenes} scenes
- Captions max 8 words with emojis
- Image prompts detailed and specific for AI image generation
{narration_note}

Respond ONLY with valid JSON, no markdown:
{{
  "title": "Catchy video title with emoji",
  "description": "One sentence description",
  "scenes": [
    {{
      "scene_number": 1,
      "description": "Visual scene description",
      "caption": "Short punchy caption with emoji",
      "narration": "Voiceover text for this scene (if applicable)",
      "image_prompt": "Detailed AI image prompt, {style} style, 4k, cinematic lighting"
    }}
  ]
}}"""

    # ─── HuggingFace API ──────────────────────────────────────────────────────

    async def _call_huggingface_api(self, prompt: str, model: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if "flan-t5" in model:
            payload = {
                "inputs": prompt[:512],
                "parameters": {"max_new_tokens": 512},
            }
        else:
            payload = {
                "inputs": f"[INST] {prompt} [/INST]",
                "parameters": {
                    "max_new_tokens": 1500,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "return_full_text": False,
                    "stop": ["</s>", "[INST]"],
                },
                "options": {"wait_for_model": False, "use_cache": True},
            }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/{model}",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            if response.status_code == 503:
                raise Exception("503 Model is loading")
            response.raise_for_status()
            result = response.json()

            if isinstance(result, list) and result:
                return result[0].get("generated_text", "")
            elif isinstance(result, dict):
                if "error" in result:
                    raise Exception(f"API error: {result['error']}")
                return result.get("generated_text", str(result))
            return str(result)

    # ─── PARSING ──────────────────────────────────────────────────────────────

    def _parse_script(self, text: str, expected_scenes: int) -> Dict[str, Any]:
        if not text:
            return {}

        try:
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                return json.loads(m.group())
        except json.JSONDecodeError:
            pass

        try:
            cleaned = re.sub(r',\s*}', '}', text)
            cleaned = re.sub(r',\s*]', ']', cleaned)
            cleaned = cleaned.replace("'", '"')
            m = re.search(r'\{[\s\S]*\}', cleaned)
            if m:
                return json.loads(m.group())
        except Exception:
            pass

        return self._fallback_parse_script(text, expected_scenes)

    def _fallback_parse_script(self, text: str, num_scenes: int) -> Dict[str, Any]:
        lines = text.strip().split("\n")
        script: Dict[str, Any] = {
            "title": "Generated Video", "description": "AI-generated content", "scenes": []
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
                    "caption": "", "image_prompt": "",
                }
            elif current_scene:
                if low.startswith("caption:"):
                    current_scene["caption"] = line.split(":", 1)[1].strip()
                elif low.startswith("image prompt:") or low.startswith("prompt:"):
                    current_scene["image_prompt"] = line.split(":", 1)[1].strip()
                elif low.startswith("narration:"):
                    current_scene["narration"] = line.split(":", 1)[1].strip()
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
        if not script.get("title"):
            script["title"] = f"Amazing {niche.title()} Content 🔥"
        if not script.get("description"):
            script["description"] = f"Discover amazing {niche} moments"
        if not script.get("scenes"):
            script["scenes"] = []

        while len(script["scenes"]) < num_scenes:
            i = len(script["scenes"]) + 1
            script["scenes"].append({
                "scene_number": i,
                "description": f"Engaging {niche} scene {i}",
                "caption": "Watch this! 🔥",
                "image_prompt": (
                    f"High quality {style} image for {niche} content, "
                    f"scene {i}, professional, detailed, 4k"
                ),
            })

        for i, scene in enumerate(script["scenes"]):
            scene["scene_number"] = i + 1
            if not scene.get("description"):
                scene["description"] = f"Scene {i + 1}: {niche} moment"
            if not scene.get("caption"):
                scene["caption"] = "Amazing! 🎯"
            if not scene.get("image_prompt"):
                scene["image_prompt"] = (
                    f"{style} style, {scene['description']}, high quality, 4k"
                )

        script["scenes"] = script["scenes"][:num_scenes]
        return script

    # ─── MOCK SCRIPT ──────────────────────────────────────────────────────────

    def _generate_rich_mock_script(
        self,
        niche: str,
        num_scenes: int,
        style: str,
        user_instructions: Optional[str] = None,
        target_platforms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        template = MOCK_TEMPLATES.get(niche.lower(), MOCK_TEMPLATES["motivation"])
        title    = template["titles"][0]
        if user_instructions:
            title = f"{title} — {user_instructions[:40]}"

        scenes = []
        for i in range(num_scenes):
            desc, caption = template["scenes"][i % len(template["scenes"])]
            scenes.append({
                "scene_number": i + 1,
                "description":  desc,
                "caption":      caption,
                "image_prompt": (
                    f"{style} style, {desc}, Nigerian/African aesthetic, "
                    f"vibrant, high quality, 4k, detailed lighting"
                ),
            })

        hashtags   = self._generate_hashtags(niche, title)
        seo_tags   = self._generate_seo_tags(niche, target_platforms or ["tiktok"])
        music_style = self._pick_music_style(niche, style)

        return {
            "title":       title,
            "description": f"Engaging {niche} content for the African audience",
            "scenes":      scenes,
            "hashtags":    hashtags,
            "seo_tags":    seo_tags,
            "music_style": music_style,
        }

    # ─── HELPERS ──────────────────────────────────────────────────────────────

    def _build_narration(self, script: Dict[str, Any], voice_style: str) -> str:
        """Build full narration string from scene descriptions."""
        scenes = script.get("scenes", [])
        parts  = []
        for scene in scenes:
            text = scene.get("narration") or scene.get("description", "")
            # FIX 3 — preserve spaces, only strip emojis and special chars
            clean = re.sub(r'[^\w\s,!?.\'-]', '', text).strip()
            if clean:
                parts.append(clean)
        return ". ".join(parts) + "."

    def _generate_hashtags(self, niche: str, title: str) -> List[str]:
        base = NICHE_HASHTAGS.get(niche.lower(), NICHE_HASHTAGS["general"]).copy()
        base.extend(NIGERIA_HASHTAGS[:2])
        for word in re.sub(r'[^\w\s]', '', title.lower()).split():
            if len(word) > 4 and f"#{word}" not in base:
                base.append(f"#{word}")
            if len(base) >= 12:
                break
        return base[:12]

    def _generate_seo_tags(
        self, niche: str, platforms: List[str]
    ) -> List[str]:
        base = [niche, "video", "content", "creator", "africa", "nigeria"]
        for p in platforms:
            base.append(p)
        return list(dict.fromkeys(base))[:10]  # deduplicate

    def _pick_music_style(self, niche: str, style: str) -> str:
        mapping = {
            "motivation": "inspirational", "fitness": "upbeat",
            "cooking": "calm",            "travel": "upbeat",
            "comedy": "upbeat",           "gaming": "epic",
            "tech": "dramatic",           "news": "dramatic",
            "music": "upbeat",            "finance": "calm",
        }
        return mapping.get(niche.lower(), "upbeat")

    def _pick_caption_style(self, style: str) -> str:
        mapping = {
            "cinematic": "modern", "cartoon": "fun",
            "realistic": "classic", "dramatic": "bold",
            "minimal": "minimal", "funny": "fun",
        }
        return mapping.get(style, "modern")

    def _detect_niche(self, idea: str) -> str:
        """Detect content niche from free-text idea string."""
        idea_lower = idea.lower()
        keywords = {
            "animals":   ["animal", "pet", "dog", "cat", "lion", "elephant", "wildlife"],
            "cooking":   ["cook", "recipe", "food", "jollof", "suya", "meal", "kitchen"],
            "tech":      ["tech", "ai", "robot", "gadget", "phone", "computer", "innovation"],
            "fitness":   ["workout", "gym", "fitness", "exercise", "muscle", "health", "body"],
            "travel":    ["travel", "trip", "vacation", "explore", "tour", "adventure", "lagos", "nigeria"],
            "gaming":    ["game", "gaming", "gamer", "play", "stream", "esport"],
            "comedy":    ["funny", "comedy", "laugh", "meme", "joke", "humor"],
            "music":     ["music", "song", "afrobeats", "artist", "concert", "beat"],
            "fashion":   ["fashion", "style", "outfit", "cloth", "ankara", "slay"],
            "finance":   ["money", "invest", "finance", "wealth", "business", "income"],
            "motivation":["motivat", "inspire", "success", "goal", "dream", "hustle"],
            "education": ["learn", "study", "fact", "school", "knowledge", "educat"],
            "news":      ["news", "breaking", "current", "today", "politic", "government"],
        }
        for niche, words in keywords.items():
            if any(w in idea_lower for w in words):
                return niche
        return "general"
