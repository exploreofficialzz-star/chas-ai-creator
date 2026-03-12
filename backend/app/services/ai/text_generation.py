"""
AI Text Generation Service — Real AI, not mock templates.
FILE: app/services/ai/text_generation.py

Calls HuggingFace Inference API (Mistral-7B-Instruct) with the user's
actual idea and generates: title, scenes, captions, hashtags, SEO tags,
narration, platform tips and post copy — all contextually relevant to
what the user typed, not hardcoded.

Fallback chain:
  1. Mistral-7B-Instruct-v0.3 (best quality, free tier)
  2. Phi-3-mini-4k-instruct     (faster, good quality)
  3. Rich rule-based generator  (offline, always works)
"""

import base64
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_HF_BASE    = "https://api-inference.huggingface.co/models"
_MODELS     = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "microsoft/Phi-3-mini-4k-instruct",
    "HuggingFaceH4/zephyr-7b-beta",
]
# Vision models for analyzing user-uploaded reference images
_VISION_MODELS = [
    "Salesforce/blip-image-captioning-large",   # Fast, reliable captions
    "nlpconnect/vit-gpt2-image-captioning",     # Fallback vision model
]
_TIMEOUT    = 45.0


class TextGenerationService:

    def __init__(self):
        from app.config import settings
        self.api_key = getattr(settings, "HUGGINGFACE_API_KEY", None) or ""

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    async def generate_script(
        self,
        niche: str,
        video_type: str         = "silent",
        duration: int           = 30,
        user_instructions: Optional[str] = None,
        style: str              = "cinematic",
        aspect_ratio: str       = "9:16",
        target_platforms: Optional[List[str]] = None,
        voice_style: str        = "professional",
        reference_images: Optional[List[str]] = None,  # List of image URLs or base64
    ) -> Dict[str, Any]:
        """
        Generate a complete video script using AI.
        If reference_images are provided, the vision model first analyzes
        them and the descriptions are injected into the script prompt so
        every scene/image prompt stays consistent with the user's visuals.
        """
        platforms   = target_platforms or ["tiktok"]
        scene_count = max(3, min(12, duration // 3))

        # Analyze uploaded reference images first
        image_context = ""
        if reference_images:
            image_context = await self._analyze_reference_images(reference_images)
            logger.info(f"Reference images analyzed: {image_context[:100]}...")

        prompt = self._build_script_prompt(
            niche=niche,
            idea=user_instructions or f"Create a {style} {niche} video",
            video_type=video_type,
            duration=duration,
            style=style,
            aspect_ratio=aspect_ratio,
            platforms=platforms,
            voice_style=voice_style,
            scene_count=scene_count,
            image_context=image_context,
        )

        raw = await self._call_ai(prompt)
        result = self._parse_script_response(raw, niche, scene_count, video_type, platforms)
        logger.info(f"Script generated: {result['title'][:50]} | {len(result['scenes'])} scenes")
        return result

    async def smart_generate_plan(
        self,
        idea: str,
        aspect_ratio: str       = "9:16",
        duration: int           = 30,
        style: str              = "cinematic",
        captions_enabled: bool  = True,
        background_music_enabled: bool = True,
        audio_mode: str         = "narration",
        voice_style: str        = "professional",
        target_platforms: Optional[List[str]] = None,
        character_consistency: bool = False,
        uploaded_image_count: int   = 0,
        reference_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Convert a natural language idea into a full video plan using AI.
        When reference_images are supplied, the vision model reads them and
        extracts subject, style, colors and setting — then injects this into
        every scene's image_prompt so the video generator reproduces the
        look & feel of the user's own photos.
        """
        platforms   = target_platforms or ["tiktok"]
        scene_count = max(3, min(12, duration // 3))

        # Step 1 — Vision analysis of uploaded reference images
        image_context     = ""
        character_desc    = ""
        visual_style_hint = ""

        if reference_images:
            logger.info(f"Analyzing {len(reference_images)} reference image(s)...")
            image_context, character_desc, visual_style_hint = \
                await self._analyze_reference_images_detailed(reference_images)
            logger.info(
                f"Image analysis: subject='{character_desc[:60]}' "
                f"style='{visual_style_hint[:60]}'"
            )

        # Step 2 — Build AI prompt with image context baked in
        prompt = self._build_smart_plan_prompt(
            idea=idea,
            aspect_ratio=aspect_ratio,
            duration=duration,
            style=style,
            audio_mode=audio_mode,
            voice_style=voice_style,
            platforms=platforms,
            scene_count=scene_count,
            captions_enabled=captions_enabled,
            image_context=image_context,
            character_desc=character_desc,
            visual_style_hint=visual_style_hint,
        )

        raw    = await self._call_ai(prompt)
        niche  = self._detect_niche(idea)
        result = self._parse_smart_plan_response(
            raw, idea, niche, aspect_ratio, duration, style,
            audio_mode, voice_style, platforms, scene_count,
        )

        # Step 3 — Post-process: append character/style context to every
        # scene's image_prompt so the image generator stays on-brand
        if character_desc or visual_style_hint:
            result = self._inject_image_context_into_scenes(
                result, character_desc, visual_style_hint, character_consistency
            )

        logger.info(
            f"Smart plan done: '{idea[:40]}' niche={niche} "
            f"ref_images={len(reference_images) if reference_images else 0}"
        )
        return result

    # ── PROMPT BUILDERS ───────────────────────────────────────────────────────

    def _build_script_prompt(
        self, niche, idea, video_type, duration, style,
        aspect_ratio, platforms, voice_style, scene_count,
        image_context: str = "",
    ) -> str:
        platform_str = ", ".join(p.capitalize() for p in platforms)
        narration_instruction = (
            f'\n- "narration": A {voice_style} voiceover line for this scene (1-2 sentences)'
            if video_type in ("narration", "sound_sync") else
            '\n- "narration": null'
        )
        image_section = (
            f"\nREFERENCE IMAGES PROVIDED BY USER:\n{image_context}\n"
            "Use the above visual descriptions to make every image_prompt "
            "consistent with the user's uploaded photos (same subject, style, colors).\n"
        ) if image_context else ""

        return f"""<s>[INST] You are a professional viral video scriptwriter specializing in short-form social media content for African and global audiences.

Create a complete video script based on this idea:
IDEA: {idea}
NICHE: {niche}
STYLE: {style}
DURATION: {duration} seconds
ASPECT RATIO: {aspect_ratio}
TARGET PLATFORMS: {platform_str}
AUDIO MODE: {video_type}
SCENES NEEDED: {scene_count}
{image_section}
Return ONLY valid JSON in this exact format, no extra text:
{{
  "title": "Catchy engaging title (max 60 chars)",
  "description": "1-2 sentence description optimized for {platform_str}",
  "scenes": [
    {{
      "scene_number": 1,
      "description": "Detailed visual scene description for image generation (what to show, colors, mood, action)",
      "caption": "Short punchy caption with 1 emoji (max 8 words)",
      "image_prompt": "Detailed AI image generation prompt for this scene"{narration_instruction},
      "duration": 3.0
    }}
  ],
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5", "#hashtag6", "#hashtag7", "#hashtag8", "#hashtag9", "#hashtag10"],
  "seo_tags": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "music_style": "upbeat|calm|dramatic|inspirational|epic|lofi|afrobeat",
  "post_caption": "Full social media post caption with hashtags for {platform_str}"
}}

Rules:
- All {scene_count} scenes must be unique and visually distinct
- image_prompt must be detailed enough for AI image generation (describe lighting, mood, colors, action)
- captions must be scroll-stopping and relatable
- hashtags must be trending and relevant to {platform_str}
- Include Nigerian/African context where appropriate
[/INST]"""

    def _build_smart_plan_prompt(
        self, idea, aspect_ratio, duration, style,
        audio_mode, voice_style, platforms, scene_count,
        captions_enabled,
        image_context: str = "",
        character_desc: str = "",
        visual_style_hint: str = "",
    ) -> str:
        platform_str = ", ".join(p.capitalize() for p in platforms)
        narration_note = (
            f"Include a {voice_style} voiceover narration for each scene."
            if audio_mode != "silent" else
            "No narration needed — visual captions only."
        )

        # Build the reference image section if user uploaded photos
        image_section = ""
        if image_context or character_desc:
            image_section = f"""
REFERENCE IMAGES UPLOADED BY USER:
{image_context}

CHARACTER/SUBJECT DETECTED: {character_desc}
VISUAL STYLE DETECTED: {visual_style_hint}

CRITICAL: Every scene's image_prompt MUST reference the above subject and visual style.
The video must look consistent with the user's uploaded photos.
Describe the same subject (person/animal/object) in every image_prompt.
"""

        return f"""<s>[INST] You are a viral content strategist and video scriptwriter for African social media creators.

A creator has this video idea: "{idea}"

Create a complete viral video plan optimized for {platform_str}.
{image_section}
SPECS:
- Duration: {duration} seconds ({scene_count} scenes)
- Aspect ratio: {aspect_ratio}
- Visual style: {style}
- Audio mode: {audio_mode}
- {narration_note}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "title": "Viral attention-grabbing title (max 60 chars, use emojis)",
  "description": "Engaging description that makes people stop scrolling",
  "niche": "detected niche from: animals|tech|cooking|motivation|fitness|travel|gaming|education|comedy|music|fashion|business|science|art|nature|finance|entertainment|news|general",
  "scenes": [
    {{
      "scene_number": 1,
      "description": "Vivid visual description of what happens in this scene",
      "caption": "Punchy caption (max 8 words + 1 emoji)",
      "image_prompt": "Detailed prompt for AI image generation: subject, setting, lighting, mood, colors, style, camera angle — MUST match reference images if provided",
      "narration": "Voiceover text if audio_mode is not silent, else null",
      "duration": 3.0
    }}
  ],
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6", "#tag7", "#tag8", "#tag9", "#tag10"],
  "seo_tags": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "music_style": "most fitting from: upbeat|calm|dramatic|inspirational|epic|lofi|afrobeat",
  "caption_style": "most fitting from: modern|classic|bold|minimal|fun",
  "post_caption": "Full ready-to-post social media caption with call-to-action and hashtags",
  "platform_tips": {{
    "tiktok":    "Specific tip for TikTok if selected",
    "instagram": "Specific tip for Instagram if selected",
    "youtube":   "Specific tip for YouTube if selected"
  }}
}}

Make every scene description and image_prompt highly specific and visually striking.
Base everything on the creator's actual idea.
[/INST]"""

    # ── AI CALLER ─────────────────────────────────────────────────────────────

    async def _call_ai(self, prompt: str) -> str:
        """Try each HuggingFace model in order, return raw text response."""
        if not self.api_key:
            logger.warning("No HUGGINGFACE_API_KEY — using offline fallback")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

        for model in _MODELS:
            try:
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens":   1200,
                        "temperature":      0.8,
                        "top_p":            0.92,
                        "do_sample":        True,
                        "return_full_text": False,
                        "stop":             ["[INST]", "</s>"],
                    },
                    "options": {
                        "wait_for_model": True,
                        "use_cache":      False,
                    },
                }

                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        f"{_HF_BASE}/{model}",
                        headers=headers,
                        json=payload,
                        timeout=_TIMEOUT,
                    )

                if r.status_code == 503:
                    logger.warning(f"{model} loading, trying next model...")
                    continue
                if r.status_code == 429:
                    logger.warning(f"{model} rate-limited, trying next model...")
                    continue
                if r.status_code != 200:
                    logger.warning(f"{model} returned {r.status_code}, trying next...")
                    continue

                data = r.json()

                # HF returns [{"generated_text": "..."}]
                if isinstance(data, list) and data:
                    text = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    text = data.get("generated_text", "")
                else:
                    text = str(data)

                if text and len(text) > 50:
                    logger.info(f"AI response from {model}: {len(text)} chars")
                    return text

            except Exception as e:
                logger.warning(f"{model} error: {e}, trying next...")
                continue

        logger.warning("All AI models failed — using offline fallback")
        return ""

    # ── VISION — REFERENCE IMAGE ANALYSIS ────────────────────────────────────

    async def _analyze_reference_images_detailed(
        self, image_sources: List[str]
    ) -> Tuple[str, str, str]:
        """
        Analyze up to 6 reference images using a vision model.
        Returns: (full_context, character_description, visual_style_hint)

        image_sources can be:
          - Cloudinary / HTTP URLs  (downloaded then base64'd)
          - data:image/...;base64,... strings (used directly)
          - raw base64 strings
        """
        captions = []
        for src in image_sources[:6]:
            try:
                img_bytes = await self._load_image_bytes(src)
                caption   = await self._call_vision_model(img_bytes)
                if caption:
                    captions.append(caption)
                    logger.info(f"Image caption: {caption[:80]}")
            except Exception as e:
                logger.warning(f"Could not analyze image: {e}")
                continue

        if not captions:
            return "", "", ""

        # Build the full context string
        full_context = "\n".join(
            f"Image {i+1}: {c}" for i, c in enumerate(captions)
        )

        # Extract character/subject description (most common subject across images)
        character_desc   = self._extract_subject(captions)
        visual_style_hint = self._extract_visual_style(captions)

        return full_context, character_desc, visual_style_hint

    async def _analyze_reference_images(self, image_sources: List[str]) -> str:
        """Simplified version — returns just the context string."""
        ctx, _, _ = await self._analyze_reference_images_detailed(image_sources)
        return ctx

    async def _load_image_bytes(self, source: str) -> bytes:
        """Load image as bytes from URL, data URI, or raw base64."""
        # data URI
        if source.startswith("data:image"):
            b64 = source.split(",", 1)[1]
            return base64.b64decode(b64)
        # raw base64 (no header)
        if not source.startswith("http"):
            try:
                return base64.b64decode(source)
            except Exception:
                pass
        # HTTP/HTTPS URL
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(source, timeout=20.0)
            r.raise_for_status()
            return r.content

    async def _call_vision_model(self, image_bytes: bytes) -> str:
        """
        Call HuggingFace BLIP captioning model with image bytes.
        Returns a natural-language description of the image.
        """
        if not self.api_key:
            return self._offline_image_description(image_bytes)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/octet-stream",
        }

        for model in _VISION_MODELS:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        f"{_HF_BASE}/{model}",
                        headers=headers,
                        content=image_bytes,
                        timeout=30.0,
                    )
                if r.status_code == 503:
                    continue   # model loading
                if r.status_code != 200:
                    continue

                data = r.json()
                # BLIP returns [{"generated_text": "..."}]
                if isinstance(data, list) and data:
                    text = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    text = data.get("generated_text", "") or data.get("label", "")
                else:
                    text = str(data)

                if text and len(text) > 5:
                    return text.strip()

            except Exception as e:
                logger.warning(f"Vision model {model} error: {e}")
                continue

        return self._offline_image_description(image_bytes)

    def _offline_image_description(self, image_bytes: bytes) -> str:
        """Fallback when vision API is unavailable — infer from file size/type."""
        size_kb = len(image_bytes) / 1024
        if size_kb > 500:
            return "High-resolution photo with detailed subject and professional lighting"
        elif size_kb > 100:
            return "Clear photo showing a subject in natural setting"
        else:
            return "Image showing a subject for reference"

    def _extract_subject(self, captions: List[str]) -> str:
        """
        Extract the most likely subject/character from image captions.
        Looks for nouns that appear consistently across multiple captions.
        """
        if not captions:
            return ""

        # Common subjects to look for
        subjects = {
            "person":   ["person", "man", "woman", "girl", "boy", "people", "human", "face", "someone"],
            "animal":   ["dog", "cat", "animal", "pet", "bird", "puppy", "kitten", "rabbit"],
            "food":     ["food", "dish", "meal", "plate", "bowl", "cake", "rice", "soup"],
            "product":  ["product", "bottle", "box", "phone", "device", "item", "object"],
            "place":    ["room", "street", "city", "building", "outdoor", "indoor", "background"],
        }

        text = " ".join(captions).lower()
        found = {}
        for subject_type, keywords in subjects.items():
            count = sum(1 for kw in keywords if kw in text)
            if count > 0:
                found[subject_type] = count

        if not found:
            # Return first 10 words of first caption as subject desc
            return " ".join(captions[0].split()[:10])

        primary = max(found, key=found.get)
        # Find the actual word from the caption
        for kw in subjects[primary]:
            if kw in text:
                # Get surrounding context
                idx = text.find(kw)
                context = text[max(0, idx-10):idx+30].strip()
                return context

        return captions[0][:60]

    def _extract_visual_style(self, captions: List[str]) -> str:
        """Extract visual style clues from image captions."""
        text = " ".join(captions).lower()

        styles = []
        if any(w in text for w in ["dark", "black", "shadow", "night"]):
            styles.append("dark moody lighting")
        if any(w in text for w in ["bright", "sunny", "outdoor", "daylight"]):
            styles.append("bright natural lighting")
        if any(w in text for w in ["colorful", "vibrant", "colorful"]):
            styles.append("vibrant colors")
        if any(w in text for w in ["close", "portrait", "face"]):
            styles.append("close-up portrait style")
        if any(w in text for w in ["wide", "landscape", "background"]):
            styles.append("wide shot")
        if any(w in text for w in ["professional", "studio", "clean"]):
            styles.append("professional studio quality")

        return ", ".join(styles) if styles else "natural photography style"

    def _inject_image_context_into_scenes(
        self,
        plan: Dict[str, Any],
        character_desc: str,
        visual_style_hint: str,
        character_consistency: bool,
    ) -> Dict[str, Any]:
        """
        Append the character description and visual style to every
        scene's image_prompt so the image_generation service produces
        visuals consistent with the user's uploaded reference photos.
        """
        if not character_desc and not visual_style_hint:
            return plan

        consistency_suffix = ""
        if character_desc:
            consistency_suffix += f", featuring {character_desc}"
        if visual_style_hint:
            consistency_suffix += f", {visual_style_hint}"
        if character_consistency:
            consistency_suffix += ", same character throughout, character consistency enabled"

        scenes = plan.get("scenes", [])
        for scene in scenes:
            original_prompt = scene.get("image_prompt", scene.get("description", ""))
            scene["image_prompt"] = f"{original_prompt}{consistency_suffix}"

        plan["scenes"] = scenes
        plan["character_description"] = character_desc
        plan["visual_style"] = visual_style_hint
        plan["reference_images_used"] = True
        return plan

    # ── RESPONSE PARSERS ──────────────────────────────────────────────────────

    def _parse_script_response(
        self, raw: str, niche: str, scene_count: int,
        video_type: str, platforms: List[str],
    ) -> Dict[str, Any]:
        """Extract JSON from AI response, fall back to offline generator."""
        data = self._extract_json(raw)
        if data:
            return self._validate_and_fill_script(data, niche, scene_count, video_type)
        # AI failed or no key — use rich offline generator
        return self._offline_generate_script(niche, scene_count, video_type, platforms)

    def _parse_smart_plan_response(
        self, raw: str, idea: str, niche: str, aspect_ratio: str,
        duration: int, style: str, audio_mode: str, voice_style: str,
        platforms: List[str], scene_count: int,
    ) -> Dict[str, Any]:
        data = self._extract_json(raw)
        if data:
            return self._validate_and_fill_plan(
                data, idea, niche, aspect_ratio, duration,
                style, audio_mode, platforms, scene_count,
            )
        return self._offline_generate_plan(
            idea, niche, aspect_ratio, duration, style,
            audio_mode, voice_style, platforms, scene_count,
        )

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Robustly extract JSON object from messy AI output."""
        if not text:
            return None

        # Strip markdown code blocks
        text = re.sub(r"```(?:json)?", "", text).strip()

        # Try direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # Find the first { ... } block
        start = text.find("{")
        if start == -1:
            return None

        # Walk forward tracking brace depth
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        # Try fixing common AI JSON mistakes
                        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)  # trailing commas
                        fixed = re.sub(r'(\w)"(\w)', r"\1'\2", fixed)     # smart quotes
                        try:
                            return json.loads(fixed)
                        except Exception:
                            pass
        return None

    def _validate_and_fill_script(
        self, data: Dict, niche: str, scene_count: int, video_type: str
    ) -> Dict[str, Any]:
        """Ensure all required fields exist and scenes are properly structured."""
        scenes = data.get("scenes", [])

        # Ensure correct scene count
        while len(scenes) < scene_count:
            n = len(scenes) + 1
            scenes.append({
                "scene_number": n,
                "description":  f"Scene {n}: Engaging visual moment",
                "caption":      f"Scene {n} 🎬",
                "image_prompt": f"Cinematic {niche} scene {n}, vibrant colors, high quality",
                "narration":    f"Scene {n} narration." if video_type != "silent" else None,
                "duration":     3.0,
            })

        # Ensure each scene has required fields
        for i, s in enumerate(scenes):
            s.setdefault("scene_number",  i + 1)
            s.setdefault("description",   f"Scene {i+1}")
            s.setdefault("caption",       f"Scene {i+1} 🎬")
            s.setdefault("image_prompt",  s.get("description", f"Scene {i+1}"))
            s.setdefault("narration",     None)
            s.setdefault("duration",      3.0)

        return {
            "title":        data.get("title",       f"Amazing {niche.capitalize()} Video"),
            "description":  data.get("description", f"Engaging {niche} content"),
            "scenes":       scenes[:scene_count],
            "narration":    data.get("narration"),
            "hashtags":     data.get("hashtags",    self._default_hashtags(niche)),
            "seo_tags":     data.get("seo_tags",    [niche, "viral", "trending"]),
            "music_style":  data.get("music_style", "upbeat"),
            "post_caption": data.get("post_caption", ""),
        }

    def _validate_and_fill_plan(
        self, data: Dict, idea: str, niche: str, aspect_ratio: str,
        duration: int, style: str, audio_mode: str,
        platforms: List[str], scene_count: int,
    ) -> Dict[str, Any]:
        filled = self._validate_and_fill_script(
            data, niche, scene_count,
            video_type=audio_mode,
        )
        filled["niche"]          = data.get("niche", niche)
        filled["caption_style"]  = data.get("caption_style", "modern")
        filled["music_style"]    = data.get("music_style", "upbeat")
        filled["post_caption"]   = data.get("post_caption", "")
        filled["platform_tips"]  = data.get("platform_tips", self._default_platform_tips(platforms))
        filled["aspect_ratio"]   = aspect_ratio
        filled["duration"]       = duration
        return filled

    # ── OFFLINE FALLBACK GENERATOR ────────────────────────────────────────────
    # Rich, idea-aware content generated without any API calls.
    # Far better than generic mock templates — uses the user's actual words.

    def _offline_generate_script(
        self, niche: str, scene_count: int,
        video_type: str, platforms: List[str],
    ) -> Dict[str, Any]:
        """Rich offline script based on niche."""
        scenes = self._niche_scenes(niche, scene_count, video_type)
        return {
            "title":        self._niche_title(niche),
            "description":  self._niche_description(niche),
            "scenes":       scenes,
            "narration":    None,
            "hashtags":     self._default_hashtags(niche),
            "seo_tags":     [niche, "viral", "trending", "africa", "content"],
            "music_style":  self._niche_music(niche),
            "post_caption": self._niche_caption(niche),
        }

    def _offline_generate_plan(
        self, idea: str, niche: str, aspect_ratio: str, duration: int,
        style: str, audio_mode: str, voice_style: str,
        platforms: List[str], scene_count: int,
    ) -> Dict[str, Any]:
        """
        Offline plan that actually uses the user's idea words to generate
        contextually relevant content — not generic templates.
        """
        idea_words = idea.lower().split()
        title      = self._idea_title(idea, niche)
        scenes     = self._idea_scenes(idea, niche, scene_count, audio_mode, voice_style)

        return {
            "title":         title,
            "description":   f"Engaging {niche} content: {idea[:80]}",
            "niche":         niche,
            "scenes":        scenes,
            "hashtags":      self._idea_hashtags(idea, niche, platforms),
            "seo_tags":      self._idea_seo_tags(idea, niche),
            "music_style":   self._niche_music(niche),
            "caption_style": self._idea_caption_style(idea),
            "post_caption":  self._idea_post_caption(idea, niche, platforms),
            "platform_tips": self._default_platform_tips(platforms),
            "aspect_ratio":  aspect_ratio,
            "duration":      duration,
        }

    # ── IDEA-AWARE HELPERS ────────────────────────────────────────────────────

    def _idea_title(self, idea: str, niche: str) -> str:
        idea_clean = idea.strip().rstrip(".,!")
        emojis = {
            "animals": "🐾", "comedy": "😂", "fitness": "💪",
            "cooking": "🍳", "tech": "💻", "motivation": "🔥",
            "travel": "✈️", "gaming": "🎮", "music": "🎵",
            "fashion": "👗", "finance": "💰", "education": "📚",
        }
        emoji = emojis.get(niche, "⭐")
        return f"{idea_clean[:50].title()} {emoji}"

    def _idea_scenes(
        self, idea: str, niche: str, count: int,
        audio_mode: str, voice_style: str,
    ) -> List[Dict]:
        """
        Generate scenes that are contextually tied to the user's idea.
        Extracts key visual concepts from the idea text.
        """
        # Extract key concepts from the idea
        keywords = [w for w in idea.lower().split()
                    if len(w) > 3 and w not in
                    {"with", "that", "this", "from", "have", "will", "your", "their"}]

        niche_visuals = {
            "animals":    ["close-up of expressive animal face", "animal playing or reacting", "animal interaction with human", "funny animal moment", "animal in natural habitat"],
            "comedy":     ["setup scene showing the situation", "reaction shot with exaggerated expression", "prank or surprise moment", "chaos ensuing", "final punchline reveal"],
            "fitness":    ["dynamic workout movement", "before/after transformation", "motivational push scene", "correct form demonstration", "victory celebration"],
            "cooking":    ["fresh ingredients laid out", "cooking action shot", "sizzling pan close-up", "plating the dish", "first bite reaction"],
            "tech":       ["device screen reveal", "feature demonstration", "comparison shot", "reaction to new tech", "life-changing moment"],
            "motivation": ["struggle scene", "turning point moment", "hard work montage", "breakthrough scene", "success and celebration"],
            "travel":     ["destination arrival shot", "local culture moment", "stunning landscape", "food or market scene", "sunset or golden hour"],
        }

        templates = niche_visuals.get(niche, [
            f"Opening hook related to: {idea[:30]}",
            f"Main content showing: {idea[:30]}",
            "Supporting visual evidence",
            "Audience engagement moment",
            "Call-to-action closing scene",
        ])

        scenes = []
        captions = self._idea_captions(idea, niche, count)
        narrations = self._idea_narrations(idea, niche, count, voice_style) if audio_mode != "silent" else [None] * count

        for i in range(count):
            template = templates[i % len(templates)]
            keyword  = keywords[i % len(keywords)] if keywords else niche

            scenes.append({
                "scene_number": i + 1,
                "description":  f"{template} — incorporating '{keyword}' from user's concept",
                "caption":      captions[i],
                "image_prompt": (
                    f"{template}, {niche} theme, {keyword} focus, "
                    f"vibrant professional photography, dramatic lighting, "
                    f"ultra-detailed, social media optimized, 4K quality"
                ),
                "narration":    narrations[i],
                "duration":     3.0,
            })

        return scenes

    def _idea_captions(self, idea: str, niche: str, count: int) -> List[str]:
        hooks = {
            "animals":    ["Wait for it... 🐾", "I can't stop watching 😭", "This is too cute 🥹", "Pure chaos 😂", "They really did this 💀", "Animals > Humans 🐶"],
            "comedy":     ["I'm deceased 💀", "This is so wrong 😂", "Nobody was ready 😭", "The audacity 😤", "Plot twist 👀", "We're not okay 😂"],
            "fitness":    ["Day 1 starts NOW 🔥", "No excuses 💪", "This hits different 😤", "The gains are real 💯", "Swipe for the secret 👇", "Results don't lie 🏆"],
            "cooking":    ["You NEED to try this 🍳", "Chef mode activated 👨‍🍳", "Easiest recipe ever 🔥", "5 minutes only ⏱️", "My grandma's secret 🤫", "Rate this dish 👇"],
            "motivation": ["This changed my life 🔥", "Stop scrolling, watch 👀", "Hard truth incoming 💯", "Your sign to start 🌟", "No more excuses 💪", "Write this down ✍️"],
        }
        captions = hooks.get(niche, [f"Scene {i+1} 🎬" for i in range(count)])
        result = []
        for i in range(count):
            result.append(captions[i % len(captions)])
        return result

    def _idea_narrations(
        self, idea: str, niche: str, count: int, voice_style: str
    ) -> List[Optional[str]]:
        """Generate contextual narration lines based on the idea."""
        styles = {
            "professional":  ["Here's what you need to know:", "Let me show you", "The key thing here is", "Watch carefully as", "This is important:"],
            "friendly":      ["Okay so get this!", "You won't believe this but", "I had to share this with you!", "Check this out!", "This is so cool —"],
            "dramatic":      ["Everything changed when...", "In that moment...", "Nothing was ever the same.", "What happened next shocked everyone.", "The truth finally revealed..."],
            "energetic":     ["LET'S GO!", "This is INSANE!", "You HAVE to see this!", "No way this is real!", "GAME CHANGER RIGHT HERE!"],
            "calm":          ["Take a moment to notice...", "Simply beautiful.", "Just breathe and observe.", "There's something special here.", "Quietly powerful."],
            "authoritative": ["Studies confirm:", "The data is clear:", "Experts agree:", "The results speak:", "Evidence shows:"],
        }
        openers = styles.get(voice_style, styles["professional"])
        idea_short = idea[:40].rstrip(".,!")
        narrations = []
        for i in range(count):
            opener = openers[i % len(openers)]
            narrations.append(f"{opener} {idea_short}, scene {i+1}.")
        return narrations

    def _idea_hashtags(self, idea: str, niche: str, platforms: List[str]) -> List[str]:
        base = self._default_hashtags(niche)
        # Extract hashtaggable words from the idea
        idea_tags = [
            f"#{w.strip('.,!?').capitalize()}"
            for w in idea.split()
            if len(w) > 4 and w.isalpha()
        ][:3]
        platform_tags = {
            "tiktok":    ["#TikTok", "#FYP", "#ForYou", "#Viral"],
            "instagram": ["#Instagram", "#Reels", "#ExploreMore"],
            "youtube":   ["#YouTubeShorts", "#Shorts"],
            "facebook":  ["#Facebook", "#FacebookReels"],
        }
        p_tags = []
        for p in platforms:
            p_tags.extend(platform_tags.get(p, [])[:2])

        all_tags = list(dict.fromkeys(base + idea_tags + p_tags))
        return all_tags[:15]

    def _idea_seo_tags(self, idea: str, niche: str) -> List[str]:
        words = [w.strip(".,!?").lower() for w in idea.split() if len(w) > 3]
        base  = [niche, "viral content", "trending", "social media", "short video"]
        return list(dict.fromkeys(words[:3] + base))[:8]

    def _idea_post_caption(self, idea: str, niche: str, platforms: List[str]) -> str:
        hashtags = " ".join(self._idea_hashtags(idea, niche, platforms)[:8])
        return f"{idea.strip()} 🔥\n\n{hashtags}\n\n👇 Share with someone who needs to see this!"

    def _idea_caption_style(self, idea: str) -> str:
        idea_l = idea.lower()
        if any(w in idea_l for w in ["funny", "comedy", "prank", "joke", "chaos"]):
            return "fun"
        if any(w in idea_l for w in ["motivat", "inspire", "hustle", "grind", "boss"]):
            return "bold"
        if any(w in idea_l for w in ["calm", "relax", "peace", "minimal", "clean"]):
            return "minimal"
        return "modern"

    # ── NICHE HELPERS ─────────────────────────────────────────────────────────

    def _detect_niche(self, text: str) -> str:
        text_l = text.lower()
        mapping = {
            "animals":     ["animal", "pet", "dog", "cat", "bird", "puppy", "kitten", "wildlife"],
            "comedy":      ["funny", "comedy", "prank", "joke", "laugh", "chaos", "reaction", "meme"],
            "fitness":     ["gym", "workout", "fitness", "muscle", "exercise", "weight", "abs"],
            "cooking":     ["food", "recipe", "cook", "eat", "meal", "jollof", "suya", "kitchen"],
            "tech":        ["tech", "phone", "app", "software", "ai", "gadget", "computer"],
            "motivation":  ["motivat", "inspire", "success", "hustle", "goal", "mindset", "dream"],
            "travel":      ["travel", "trip", "tour", "explore", "vacation", "lagos", "abuja"],
            "gaming":      ["game", "gaming", "gamer", "play", "esport", "stream"],
            "music":       ["music", "song", "beat", "sing", "rap", "afrobeat", "artist"],
            "fashion":     ["fashion", "style", "outfit", "wear", "clothes", "ootd"],
            "finance":     ["money", "invest", "crypto", "wealth", "income", "naira", "salary"],
            "education":   ["learn", "study", "teach", "tips", "facts", "how to", "tutorial"],
            "nature":      ["nature", "forest", "ocean", "mountain", "plant", "environment"],
            "business":    ["business", "startup", "brand", "entrepreneur", "market", "sales"],
        }
        for niche, keywords in mapping.items():
            if any(kw in text_l for kw in keywords):
                return niche
        return "general"

    def _niche_title(self, niche: str) -> str:
        return {
            "animals":     "Adorable Animal Moments That Will Melt Your Heart 🐾",
            "comedy":      "This Had Me Crying Laughing 😂",
            "fitness":     "Transform Your Body With This Routine 💪",
            "cooking":     "This Recipe Will Change Your Life 🍳",
            "tech":        "This Tech Will Blow Your Mind 💻",
            "motivation":  "Watch This When You Feel Like Giving Up 🔥",
            "travel":      "Hidden Gems You Need to Visit ✈️",
            "gaming":      "This Gaming Moment Is Unreal 🎮",
            "music":       "This Beat Is Everything 🎵",
            "fashion":     "Outfit Ideas That Always Hit 👗",
            "finance":     "How I Made Money While Sleeping 💰",
            "education":   "Facts That Will Blow Your Mind 📚",
        }.get(niche, "You Won't Believe This ⭐")

    def _niche_description(self, niche: str) -> str:
        return f"Engaging {niche} content for the African audience 🌍"

    def _niche_music(self, niche: str) -> str:
        return {
            "animals": "upbeat", "comedy": "upbeat", "fitness": "energetic",
            "cooking": "upbeat", "tech": "upbeat", "motivation": "inspirational",
            "travel": "upbeat", "gaming": "epic", "music": "upbeat",
            "fashion": "upbeat", "finance": "inspirational", "education": "calm",
            "nature": "calm", "drama": "dramatic",
        }.get(niche, "upbeat")

    def _niche_caption(self, niche: str) -> str:
        return f"Amazing {niche} content! 🔥 Drop a ❤️ if this helped!\n\n" + \
               " ".join(self._default_hashtags(niche)[:6])

    def _niche_scenes(
        self, niche: str, count: int, video_type: str
    ) -> List[Dict]:
        templates = {
            "animals":    ["Fluffy puppy discovering snow for the first time", "Tiny kitten chasing its tail in circles", "Baby elephant splashing water with its trunk", "Parrot perfectly mimicking human laughter", "Rabbit doing binkies in a sunny garden"],
            "comedy":     ["Dramatic slow-motion fail in unexpected situation", "Epic reaction to surprising news", "Prank gone hilariously wrong", "Accidental chaos erupting", "Confused animal doing human things"],
            "fitness":    ["Explosive power movement at sunrise gym", "Transformation reveal before and after", "Intense sweat-dripping workout", "Perfect form demonstration close-up", "Victory pose at workout completion"],
            "cooking":    ["Fresh colorful ingredients arranged beautifully", "Hot oil sizzling with aromatic spices", "Chef's hands expertly plating dish", "Steam rising from perfectly cooked jollof rice", "First bite reaction of pure satisfaction"],
            "motivation": ["Person waking up before sunrise determined", "Grinding in an empty gym alone", "Turning point breakthrough moment", "Achievement and celebration scene", "Inspiring message on screen"],
            "travel":     ["Breathtaking landscape at golden hour", "Vibrant local market full of colors", "Trying exotic street food for first time", "Discovering a hidden scenic viewpoint", "Sunset over African savanna"],
            "tech":       ["Unboxing latest device with excitement", "Mind-blowing feature demonstration", "Before vs after using the tech", "Futuristic interface interaction", "Satisfied user reaction shot"],
        }
        scenes_list = templates.get(niche, [f"Scene {i+1} visual" for i in range(count)])

        scenes = []
        for i in range(count):
            desc = scenes_list[i % len(scenes_list)]
            scenes.append({
                "scene_number": i + 1,
                "description":  desc,
                "caption":      self._idea_captions("", niche, count)[i],
                "image_prompt": (
                    f"{desc}, {niche} photography, professional studio lighting, "
                    f"ultra sharp, vibrant colors, social media optimized, 8K quality"
                ),
                "narration":    f"Scene {i+1}." if video_type != "silent" else None,
                "duration":     3.0,
            })
        return scenes

    def _default_hashtags(self, niche: str) -> List[str]:
        base = ["#Viral", "#FYP", "#Trending", "#Africa", "#Nigeria", "#Content"]
        niche_tags = {
            "animals":    ["#Animals", "#Pets", "#CutePets", "#FunnyAnimals", "#PetLovers"],
            "comedy":     ["#Comedy", "#Funny", "#Laugh", "#Memes", "#Humor"],
            "fitness":    ["#Fitness", "#Gym", "#Workout", "#FitLife", "#Gains"],
            "cooking":    ["#Food", "#Cooking", "#Recipe", "#FoodLovers", "#Foodie"],
            "tech":       ["#Tech", "#Technology", "#Gadgets", "#Innovation", "#AI"],
            "motivation": ["#Motivation", "#Hustle", "#Success", "#Mindset", "#Goals"],
            "travel":     ["#Travel", "#Explore", "#Adventure", "#Wanderlust", "#Tourism"],
            "finance":    ["#Finance", "#Money", "#Investment", "#Wealth", "#Business"],
            "music":      ["#Music", "#Afrobeat", "#NewMusic", "#Artist", "#Vibes"],
            "fashion":    ["#Fashion", "#Style", "#OOTD", "#Outfit", "#Fashionista"],
        }
        return list(dict.fromkeys(niche_tags.get(niche, ["#Viral"]) + base))[:12]

    def _default_platform_tips(self, platforms: List[str]) -> Dict[str, str]:
        tips = {
            "tiktok":    "Post between 7–9 PM WAT for maximum reach. Use trending sounds.",
            "instagram": "Add to Reels with a strong first frame. Post to Stories too.",
            "youtube":   "Write a keyword-rich description. Add chapters for retention.",
            "facebook":  "Upload natively (not shared from TikTok) for more reach.",
            "twitter":   "Keep under 2:20. Add captions — 85% watch without sound.",
            "linkedin":  "Add professional context in the caption. Tag relevant people.",
        }
        return {p: tips[p] for p in platforms if p in tips}
