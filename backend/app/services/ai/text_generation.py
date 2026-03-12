"""
AI Text Generation Service — Multi-Provider, Zero Hardcoded Text.
FILE: app/services/ai/text_generation.py

Provider chain (tried in order, first success wins):
  1. HuggingFace  — Qwen2.5-7B, Mistral-7B, Zephyr-7B, Phi-3.5
  2. Groq         — llama-3.1-70b, mixtral-8x7b, gemma2-9b  (fastest free tier)
  3. Google Gemini— gemini-1.5-flash (generous free tier)
  4. OpenAI       — gpt-4o-mini, gpt-3.5-turbo

If EVERY provider fails → raises AIGenerationError.
No hardcoded text is EVER returned to the user.

Vision chain (reference image analysis):
  1. HuggingFace BLIP / ViT-GPT2
  2. Gemini Vision (gemini-1.5-flash handles images natively)

Required .env keys (at least ONE must be set):
  HUGGINGFACE_API_KEY
  GROQ_API_KEY
  GEMINI_API_KEY
  OPENAI_API_KEY
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Custom exception ──────────────────────────────────────────────────────────

class AIGenerationError(Exception):
    """Raised when every AI provider fails — never return hardcoded text."""


# ── Endpoints ─────────────────────────────────────────────────────────────────

_HF_BASE    = "https://api-inference.huggingface.co/models"
_GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# HuggingFace text models  (model_id, prompt_format)
_HF_MODELS: List[Tuple[str, str]] = [
    ("Qwen/Qwen2.5-7B-Instruct",           "chatml"),
    ("mistralai/Mistral-7B-Instruct-v0.3", "mistral"),
    ("HuggingFaceH4/zephyr-7b-beta",       "zephyr"),
    ("microsoft/Phi-3.5-mini-instruct",    "chatml"),
]

_GROQ_MODELS   = ["llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
_GEMINI_MODELS = ["gemini-1.5-flash", "gemini-1.5-flash-8b"]
_OPENAI_MODELS = ["gpt-4o-mini", "gpt-3.5-turbo"]

_HF_VISION_MODELS = [
    "Salesforce/blip-image-captioning-large",
    "nlpconnect/vit-gpt2-image-captioning",
]

_TIMEOUT        = 60.0
_VISION_TIMEOUT = 30.0
_HF_RETRY_DELAY = 8.0
_HF_MAX_RETRY   = 2


# ── Prompt formatter ──────────────────────────────────────────────────────────

def _fmt(system: str, user: str, fmt: str) -> str:
    if fmt == "chatml":
        return (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{user}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    if fmt == "mistral":
        return f"<s>[INST] {system}\n\n{user} [/INST]"
    if fmt == "zephyr":
        return (
            f"<|system|>\n{system}</s>\n"
            f"<|user|>\n{user}</s>\n"
            f"<|assistant|>\n"
        )
    return f"### System:\n{system}\n\n### User:\n{user}\n\n### Assistant:\n"


# ── Main service ──────────────────────────────────────────────────────────────

class TextGenerationService:

    def __init__(self):
        from app.config import settings
        self.hf_key     = getattr(settings, "HUGGINGFACE_API_KEY", "") or ""
        self.groq_key   = getattr(settings, "GROQ_API_KEY",        "") or ""
        self.gemini_key = getattr(settings, "GEMINI_API_KEY",      "") or ""
        self.openai_key = getattr(settings, "OPENAI_API_KEY",      "") or ""

        active = [k for k, v in {
            "HuggingFace": self.hf_key, "Groq": self.groq_key,
            "Gemini": self.gemini_key,  "OpenAI": self.openai_key,
        }.items() if v]

        if not active:
            logger.error(
                "NO AI KEYS SET — generation will fail. "
                "Set at least one of: HUGGINGFACE_API_KEY, GROQ_API_KEY, "
                "GEMINI_API_KEY, OPENAI_API_KEY"
            )
        else:
            logger.info(f"AI providers active: {', '.join(active)}")

    # ── Public methods ────────────────────────────────────────────────────────

    async def generate_script(
        self,
        niche: str,
        video_type: str = "silent",
        duration: int = 30,
        user_instructions: Optional[str] = None,
        style: str = "cinematic",
        aspect_ratio: str = "9:16",
        target_platforms: Optional[List[str]] = None,
        voice_style: str = "professional",
        reference_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        platforms   = target_platforms or ["tiktok"]
        scene_count = _clamp(duration)
        idea        = user_instructions or f"Create a {style} {niche} video"

        image_context = ""
        if reference_images:
            image_context = await self._analyze_images(reference_images)

        sys_msg, usr_msg = _script_prompt(
            niche, idea, video_type, duration, style,
            aspect_ratio, platforms, voice_style, scene_count, image_context,
        )
        raw    = await self._call_ai(sys_msg, usr_msg)
        result = _parse_script(raw, idea, niche, scene_count, video_type)
        logger.info(f"Script ready: '{result['title'][:50]}' | {len(result['scenes'])} scenes")
        return result

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
        reference_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        platforms   = target_platforms or ["tiktok"]
        scene_count = _clamp(duration)

        image_context = char_desc = style_hint = ""
        if reference_images:
            logger.info(f"Analyzing {len(reference_images)} reference image(s)…")
            image_context, char_desc, style_hint = (
                await self._analyze_images_detailed(reference_images)
            )

        sys_msg, usr_msg = _plan_prompt(
            idea, aspect_ratio, duration, style, audio_mode, voice_style,
            platforms, scene_count, captions_enabled,
            image_context, char_desc, style_hint,
        )
        raw    = await self._call_ai(sys_msg, usr_msg)
        niche  = _niche(idea)
        result = _parse_plan(
            raw, idea, niche, aspect_ratio, duration,
            style, audio_mode, platforms, scene_count,
        )

        if char_desc or style_hint:
            result = _inject_vision(result, char_desc, style_hint, character_consistency)

        logger.info(
            f"Plan ready: '{idea[:40]}' | niche={niche} "
            f"| scenes={len(result['scenes'])}"
        )
        return result

    # ── Provider chain ────────────────────────────────────────────────────────

    async def _call_ai(self, system: str, user_msg: str) -> str:
        errors: List[str] = []

        if self.hf_key:
            try:
                t = await self._hf_text(system, user_msg)
                if t:
                    return t
            except Exception as e:
                errors.append(f"HuggingFace: {e}")

        if self.groq_key:
            try:
                t = await self._oai_compat(
                    _GROQ_URL, self.groq_key, _GROQ_MODELS, system, user_msg, "Groq"
                )
                if t:
                    return t
            except Exception as e:
                errors.append(f"Groq: {e}")

        if self.gemini_key:
            try:
                t = await self._gemini_text(system, user_msg)
                if t:
                    return t
            except Exception as e:
                errors.append(f"Gemini: {e}")

        if self.openai_key:
            try:
                t = await self._oai_compat(
                    _OPENAI_URL, self.openai_key, _OPENAI_MODELS, system, user_msg, "OpenAI"
                )
                if t:
                    return t
            except Exception as e:
                errors.append(f"OpenAI: {e}")

        raise AIGenerationError(
            "All AI providers are currently unavailable. Please try again shortly. "
            f"Details: {' | '.join(errors) if errors else 'No API keys configured'}"
        )

    # ── HuggingFace text ──────────────────────────────────────────────────────

    async def _hf_text(self, system: str, user_msg: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.hf_key}",
            "Content-Type": "application/json",
        }
        for model_id, prompt_fmt in _HF_MODELS:
            prompt  = _fmt(system, user_msg, prompt_fmt)
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 1400, "temperature": 0.75,
                    "top_p": 0.90, "repetition_penalty": 1.1,
                    "do_sample": True, "return_full_text": False,
                    "stop_sequences": ["[INST]", "<|im_start|>", "<|user|>"],
                },
                "options": {"wait_for_model": True, "use_cache": False},
            }
            for attempt in range(_HF_MAX_RETRY + 1):
                try:
                    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                        r = await c.post(f"{_HF_BASE}/{model_id}", headers=headers, json=payload)
                    if r.status_code == 503:
                        if attempt < _HF_MAX_RETRY:
                            logger.info(f"HF {model_id} warming… retry {attempt+1}")
                            await asyncio.sleep(_HF_RETRY_DELAY)
                            continue
                        break
                    if r.status_code == 429:
                        logger.warning(f"HF {model_id} rate-limited")
                        break
                    if r.status_code != 200:
                        logger.warning(f"HF {model_id} HTTP {r.status_code}")
                        break
                    t = _hf_text(r.json())
                    if t and len(t) > 30:
                        logger.info(f"✓ HF/{model_id} ({len(t)} chars)")
                        return t
                    break
                except httpx.TimeoutException:
                    logger.warning(f"HF {model_id} timeout")
                    if attempt < _HF_MAX_RETRY:
                        await asyncio.sleep(3.0)
                    continue
                except Exception as e:
                    logger.warning(f"HF {model_id}: {e}")
                    break
        return ""

    # ── OpenAI-compatible (Groq + OpenAI) ────────────────────────────────────

    async def _oai_compat(
        self, url: str, key: str, models: List[str],
        system: str, user_msg: str, provider: str,
    ) -> str:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        for model in models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_msg},
                ],
                "max_tokens": 1400, "temperature": 0.75, "top_p": 0.90,
            }
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    r = await c.post(url, headers=headers, json=payload)
                if r.status_code == 429:
                    logger.warning(f"{provider}/{model} rate-limited")
                    await asyncio.sleep(2.0)
                    continue
                if r.status_code != 200:
                    logger.warning(f"{provider}/{model} HTTP {r.status_code}: {r.text[:100]}")
                    continue
                t = (
                    r.json().get("choices", [{}])[0]
                     .get("message", {}).get("content", "") or ""
                )
                if t and len(t) > 30:
                    logger.info(f"✓ {provider}/{model} ({len(t)} chars)")
                    return t.strip()
            except httpx.TimeoutException:
                logger.warning(f"{provider}/{model} timed out")
            except Exception as e:
                logger.warning(f"{provider}/{model}: {e}")
        return ""

    # ── Gemini text ───────────────────────────────────────────────────────────

    async def _gemini_text(self, system: str, user_msg: str) -> str:
        for model in _GEMINI_MODELS:
            url     = _GEMINI_URL.format(model=model)
            payload = {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                "generationConfig": {
                    "maxOutputTokens": 1400, "temperature": 0.75, "topP": 0.90,
                },
            }
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    r = await c.post(url, params={"key": self.gemini_key}, json=payload)
                if r.status_code == 429:
                    logger.warning(f"Gemini/{model} rate-limited")
                    await asyncio.sleep(2.0)
                    continue
                if r.status_code != 200:
                    logger.warning(f"Gemini/{model} HTTP {r.status_code}")
                    continue
                t = (
                    r.json().get("candidates", [{}])[0]
                     .get("content", {}).get("parts", [{}])[0]
                     .get("text", "") or ""
                )
                if t and len(t) > 30:
                    logger.info(f"✓ Gemini/{model} ({len(t)} chars)")
                    return t.strip()
            except httpx.TimeoutException:
                logger.warning(f"Gemini/{model} timed out")
            except Exception as e:
                logger.warning(f"Gemini/{model}: {e}")
        return ""

    # ── Vision ────────────────────────────────────────────────────────────────

    async def _analyze_images_detailed(
        self, sources: List[str]
    ) -> Tuple[str, str, str]:
        captions: List[str] = []
        for src in sources[:6]:
            try:
                img = await _load_image(src)
                cap = await self._vision(img)
                if cap:
                    captions.append(cap)
                    logger.info(f"Vision: {cap[:80]}")
            except Exception as e:
                logger.warning(f"Image analysis failed: {e}")

        if not captions:
            raise AIGenerationError(
                "Could not analyze the uploaded reference images. "
                "Please ensure HUGGINGFACE_API_KEY or GEMINI_API_KEY is set."
            )
        ctx   = "\n".join(f"Image {i+1}: {c}" for i, c in enumerate(captions))
        subj  = _subject(captions)
        style = _vstyle(captions)
        return ctx, subj, style

    async def _analyze_images(self, sources: List[str]) -> str:
        ctx, _, _ = await self._analyze_images_detailed(sources)
        return ctx

    async def _vision(self, img: bytes) -> str:
        # 1. HF vision
        if self.hf_key:
            t = await self._hf_vision(img)
            if t:
                return t
        # 2. Gemini vision
        if self.gemini_key:
            t = await self._gemini_vision(img)
            if t:
                return t
        raise AIGenerationError(
            "No vision provider available. Set HUGGINGFACE_API_KEY or GEMINI_API_KEY."
        )

    async def _hf_vision(self, img: bytes) -> str:
        headers = {
            "Authorization": f"Bearer {self.hf_key}",
            "Content-Type": "application/octet-stream",
        }
        for model in _HF_VISION_MODELS:
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=_VISION_TIMEOUT) as c:
                        r = await c.post(f"{_HF_BASE}/{model}", headers=headers, content=img)
                    if r.status_code == 503:
                        if attempt == 0:
                            await asyncio.sleep(5.0)
                            continue
                        break
                    if r.status_code != 200:
                        break
                    t = _hf_text(r.json())
                    if t and len(t) > 5:
                        return t.strip()
                    break
                except Exception as e:
                    logger.warning(f"HF vision {model}: {e}")
                    break
        return ""

    async def _gemini_vision(self, img: bytes) -> str:
        b64  = base64.b64encode(img).decode()
        mime = "image/jpeg"
        if img[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif img[:4] == b"RIFF" and img[8:12] == b"WEBP":
            mime = "image/webp"
        url     = _GEMINI_URL.format(model="gemini-1.5-flash")
        payload = {
            "contents": [{"role": "user", "parts": [
                {"text": "Describe this image: subject, setting, lighting, colours, mood. Be specific."},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]}],
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0.4},
        }
        try:
            async with httpx.AsyncClient(timeout=_VISION_TIMEOUT) as c:
                r = await c.post(url, params={"key": self.gemini_key}, json=payload)
            if r.status_code != 200:
                return ""
            t = (
                r.json().get("candidates", [{}])[0]
                 .get("content", {}).get("parts", [{}])[0]
                 .get("text", "") or ""
            )
            if t and len(t) > 5:
                logger.info(f"✓ Gemini vision ({len(t)} chars)")
                return t.strip()
        except Exception as e:
            logger.warning(f"Gemini vision: {e}")
        return ""


# ── Prompt builders ───────────────────────────────────────────────────────────

def _script_prompt(
    niche, idea, video_type, duration, style,
    aspect_ratio, platforms, voice_style, scene_count, image_context,
) -> Tuple[str, str]:
    pstr  = ", ".join(p.capitalize() for p in platforms)
    nfld  = (
        f'"narration": "A {voice_style} voiceover for this scene (1-2 sentences)"'
        if video_type in ("narration", "sound_sync") else '"narration": null'
    )
    imgs  = (
        f"\nREFERENCE IMAGES (keep every image_prompt consistent):\n{image_context}\n"
        if image_context else ""
    )
    system = (
        "You are a professional viral video scriptwriter. "
        "Output ONLY valid JSON — no markdown, no prose, no code fences."
    )
    user = f"""{imgs}Create a complete video script for this idea:

IDEA: {idea}
NICHE: {niche}  |  STYLE: {style}  |  DURATION: {duration}s ({scene_count} scenes)
ASPECT RATIO: {aspect_ratio}  |  PLATFORMS: {pstr}  |  AUDIO: {video_type}

Return ONLY this JSON:
{{
  "title": "<catchy title ≤60 chars, specific to the idea>",
  "description": "<1-2 sentence description for {pstr}>",
  "scenes": [
    {{
      "scene_number": 1,
      "description": "<vivid, specific visual tied to '{idea}'>",
      "caption": "<scroll-stopping ≤8 words + 1 emoji>",
      "image_prompt": "<detailed AI image prompt: subject, action, setting, lighting, mood, colours, angle>",
      {nfld},
      "duration": 3.0
    }}
    // repeat for ALL {scene_count} scenes
  ],
  "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8","#tag9","#tag10"],
  "seo_tags": ["kw1","kw2","kw3","kw4","kw5"],
  "music_style": "upbeat|calm|dramatic|inspirational|epic|lofi|afrobeat",
  "post_caption": "<ready-to-post caption with hashtags and CTA>"
}}"""
    return system, user


def _plan_prompt(
    idea, aspect_ratio, duration, style, audio_mode, voice_style,
    platforms, scene_count, captions_enabled,
    image_context, char_desc, style_hint,
) -> Tuple[str, str]:
    pstr  = ", ".join(p.capitalize() for p in platforms)
    nline = (
        f"Each scene MUST have a {voice_style} voiceover in 'narration'."
        if audio_mode != "silent" else "Set every 'narration' to null."
    )
    imgs  = ""
    if image_context or char_desc:
        imgs = (
            f"\nREFERENCE IMAGES:\n{image_context}\n"
            f"SUBJECT: {char_desc}\nSTYLE: {style_hint}\n"
            "Every image_prompt MUST reference this subject and visual style.\n"
        )
    system = (
        "You are a viral content strategist for African social media creators. "
        "Output ONLY valid JSON — no markdown, no code fences, no prose. "
        "Every scene must be DIRECTLY and SPECIFICALLY about the creator's idea."
    )
    user = f"""{imgs}Creator's idea: "{idea}"

Build a complete viral video plan for {pstr}.

SPECS: {duration}s | {scene_count} scenes | {aspect_ratio} | {style} | {audio_mode}
{nline}

Return ONLY valid JSON:
{{
  "title": "<viral title about '{idea}' ≤60 chars, 1-2 emojis>",
  "description": "<specific description about '{idea}', makes people stop scrolling>",
  "niche": "animals|tech|cooking|motivation|fitness|travel|gaming|education|comedy|music|fashion|business|science|art|nature|finance|entertainment|news|general",
  "scenes": [
    {{
      "scene_number": 1,
      "description": "<specific scene directly from '{idea}'>",
      "caption": "<punchy ≤8 words + 1 emoji, tied to the idea>",
      "image_prompt": "<AI image prompt: exact subject, setting, action, lighting, mood, colours, camera angle>",
      "narration": "<voiceover or null>",
      "duration": 3.0
    }}
    // ALL {scene_count} scenes
  ],
  "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8","#tag9","#tag10"],
  "seo_tags": ["kw1","kw2","kw3","kw4","kw5"],
  "music_style": "upbeat|calm|dramatic|inspirational|epic|lofi|afrobeat",
  "caption_style": "modern|classic|bold|minimal|fun",
  "post_caption": "<full caption with CTA + hashtags>",
  "platform_tips": {{
    "tiktok": "<tip if selected>",
    "instagram": "<tip if selected>",
    "youtube": "<tip if selected>"
  }}
}}"""
    return system, user


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_script(
    raw: str, idea: str, niche: str, scene_count: int, video_type: str
) -> Dict[str, Any]:
    data = _json(raw)
    if not data:
        raise AIGenerationError("AI returned an unreadable response. Please try again.")
    return _fill_script(data, idea, niche, scene_count, video_type)


def _parse_plan(
    raw: str, idea: str, niche: str, aspect_ratio: str, duration: int,
    style: str, audio_mode: str, platforms: List[str], scene_count: int,
) -> Dict[str, Any]:
    data = _json(raw)
    if not data:
        raise AIGenerationError("AI returned an unreadable response. Please try again.")
    return _fill_plan(data, idea, niche, aspect_ratio, duration, style, audio_mode, platforms, scene_count)


def _fill_script(
    data: Dict, idea: str, niche: str, scene_count: int, video_type: str
) -> Dict[str, Any]:
    scenes = _pad(data.get("scenes", []), scene_count, idea, niche, video_type)
    for i, s in enumerate(scenes):
        s.setdefault("scene_number", i + 1)
        s.setdefault("description",  f"Scene {i+1}: {idea[:50]}")
        s.setdefault("caption",      f"Scene {i+1} 🎬")
        s.setdefault("image_prompt", s.get("description", ""))
        s.setdefault("narration",    None)
        s.setdefault("duration",     3.0)
    return {
        "title":        data["title"],
        "description":  data.get("description", ""),
        "scenes":       scenes[:scene_count],
        "narration":    data.get("narration"),
        "hashtags":     data.get("hashtags", []),
        "seo_tags":     data.get("seo_tags", []),
        "music_style":  data.get("music_style", "upbeat"),
        "post_caption": data.get("post_caption", ""),
    }


def _fill_plan(
    data: Dict, idea: str, niche: str, aspect_ratio: str, duration: int,
    style: str, audio_mode: str, platforms: List[str], scene_count: int,
) -> Dict[str, Any]:
    base = _fill_script(data, idea, niche, scene_count, audio_mode)
    base.update({
        "niche":         data.get("niche", niche),
        "caption_style": data.get("caption_style", "modern"),
        "music_style":   data.get("music_style", "upbeat"),
        "post_caption":  data.get("post_caption", ""),
        "platform_tips": data.get("platform_tips", _platform_tips(platforms)),
        "aspect_ratio":  aspect_ratio,
        "duration":      duration,
    })
    return base


def _pad(
    scenes: List[Dict], target: int,
    idea: str, niche: str, video_type: str,
) -> List[Dict]:
    while len(scenes) < target:
        n = len(scenes) + 1
        logger.warning(f"AI returned fewer scenes than requested — padding scene {n}")
        scenes.append({
            "scene_number": n,
            "description":  f"Scene {n}: {idea[:60]}",
            "caption":      f"Part {n} 🎬",
            "image_prompt": (
                f"Scene {n} for '{idea[:50]}', {niche} theme, "
                "cinematic lighting, ultra-detailed, 4K"
            ),
            "narration":    None,
            "duration":     3.0,
        })
    return scenes


# ── JSON extraction ───────────────────────────────────────────────────────────

def _json(text: str) -> Optional[Dict]:
    if not text:
        return None
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = end = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    candidate = text[start: end + 1] if end else text[start:] + "\n}"
    candidate = _fix(candidate)
    try:
        return json.loads(candidate)
    except Exception as e:
        logger.debug(f"JSON repair failed: {e} | {candidate[:100]}")
        return None


def _fix(s: str) -> str:
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = re.sub(r"(?<![\\])'", '"', s)
    s = re.sub(
        r'("(?:[^"\\]|\\.)*?")',
        lambda m: m.group(0).replace("\n", "\\n"), s,
    )
    s = s.replace(": None", ": null").replace(": True", ": true").replace(": False", ": false")
    s = re.sub(r"//[^\n]*", "", s)
    return s


# ── Utilities ─────────────────────────────────────────────────────────────────

def _clamp(duration: int) -> int:
    return max(3, min(12, duration // 3))


def _hf_text(data: Any) -> str:
    if isinstance(data, list) and data:
        item = data[0]
        return (item.get("generated_text", "") or item.get("label", "")) if isinstance(item, dict) else str(item)
    if isinstance(data, dict):
        return data.get("generated_text", "") or data.get("text", "") or data.get("label", "")
    return str(data) if data else ""


def _niche(text: str) -> str:
    tl = text.lower()
    MAP = {
        "animals":   ["animal","pet","dog","cat","bird","puppy","kitten","wildlife"],
        "comedy":    ["funny","comedy","prank","joke","laugh","chaos","meme"],
        "fitness":   ["gym","workout","fitness","muscle","exercise","abs","cardio"],
        "cooking":   ["food","recipe","cook","eat","meal","jollof","suya","kitchen"],
        "tech":      ["tech","phone","app","software","ai","gadget","computer"],
        "motivation":["motivat","inspire","success","hustle","goal","mindset"],
        "travel":    ["travel","trip","tour","explore","vacation","lagos","abuja"],
        "gaming":    ["game","gaming","gamer","play","esport","stream"],
        "music":     ["music","song","beat","sing","rap","afrobeat","artist"],
        "fashion":   ["fashion","style","outfit","wear","clothes","ootd"],
        "finance":   ["money","invest","crypto","wealth","income","naira"],
        "education": ["learn","study","teach","tips","facts","how to","tutorial"],
        "nature":    ["nature","forest","ocean","mountain","plant","environment"],
        "business":  ["business","startup","brand","entrepreneur","market"],
    }
    for n, kws in MAP.items():
        if any(k in tl for k in kws):
            return n
    return "general"


def _platform_tips(platforms: List[str]) -> Dict[str, str]:
    TIPS = {
        "tiktok":    "Post 7–9 PM WAT. Use a trending sound. Hook in the first second.",
        "instagram": "Post Reels + Stories simultaneously. Strong first frame wins.",
        "youtube":   "Write a keyword-rich description. Add chapter timestamps.",
        "facebook":  "Upload natively — never share from TikTok. Native gets 3× reach.",
        "twitter":   "Keep under 2:20. 85% watch without sound — add captions.",
        "linkedin":  "Add professional context in the caption. Tag relevant people.",
    }
    return {p: TIPS[p] for p in platforms if p in TIPS}


async def _load_image(source: str) -> bytes:
    if source.startswith("data:image"):
        return base64.b64decode(source.split(",", 1)[1] + "==")
    if not source.startswith("http"):
        try:
            return base64.b64decode(source + "==")
        except Exception:
            pass
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as c:
        r = await c.get(source)
        r.raise_for_status()
        return r.content


def _subject(captions: List[str]) -> str:
    if not captions:
        return ""
    SUBS = {
        "person":  ["person","man","woman","girl","boy","people","face","portrait"],
        "animal":  ["dog","cat","animal","pet","bird","puppy","kitten","wildlife"],
        "food":    ["food","dish","meal","plate","bowl","cake","rice","soup"],
        "product": ["product","bottle","box","phone","device","object"],
        "place":   ["room","street","city","building","outdoor","landscape"],
    }
    text  = " ".join(captions).lower()
    found = {st: sum(1 for kw in kws if kw in text) for st, kws in SUBS.items()}
    found = {k: v for k, v in found.items() if v}
    if not found:
        return " ".join(captions[0].split()[:10])
    primary = max(found, key=found.get)
    for kw in SUBS[primary]:
        if kw in text:
            idx = text.find(kw)
            return text[max(0, idx - 10): idx + 35].strip()
    return captions[0][:60]


def _vstyle(captions: List[str]) -> str:
    text   = " ".join(captions).lower()
    styles = []
    if any(w in text for w in ["dark","shadow","night","moody"]):
        styles.append("dark moody lighting")
    if any(w in text for w in ["bright","sunny","outdoor","daylight"]):
        styles.append("bright natural lighting")
    if any(w in text for w in ["colorful","vibrant","vivid"]):
        styles.append("vibrant colours")
    if any(w in text for w in ["close","portrait","face","macro"]):
        styles.append("close-up portrait style")
    if any(w in text for w in ["wide","landscape","panoramic"]):
        styles.append("wide cinematic shot")
    if any(w in text for w in ["professional","studio","clean"]):
        styles.append("professional studio quality")
    return ", ".join(styles) if styles else "natural photography style"


def _inject_vision(
    plan: Dict[str, Any],
    char_desc: str, style_hint: str,
    character_consistency: bool,
) -> Dict[str, Any]:
    suffix = ""
    if char_desc:
        suffix += f", featuring {char_desc}"
    if style_hint:
        suffix += f", {style_hint}"
    if character_consistency:
        suffix += ", same character throughout, character consistency enabled"
    for scene in plan.get("scenes", []):
        base = scene.get("image_prompt") or scene.get("description", "")
        scene["image_prompt"] = f"{base}{suffix}"
    plan["character_description"] = char_desc
    plan["visual_style"]          = style_hint
    plan["reference_images_used"] = True
    return plan
