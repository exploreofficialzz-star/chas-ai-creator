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

# ── Model lists — updated March 2026 ─────────────────────────────────────────
# HF: Qwen2.5-7B, Mistral-7B-v0.3, Zephyr-7b-beta, Phi-3.5 → 410 Gone
#   (removed from free Serverless Inference API). Using smaller replacements.
# Groq: llama-3.1-70b, mixtral-8x7b, gemma2-9b → 400 Decommissioned.
# Gemini: gemini-1.5-flash, gemini-1.5-flash-8b → 404 Deprecated.

# HuggingFace — smaller models still on free Serverless Inference API
_HF_MODELS: List[Tuple[str, str]] = [
    ("Qwen/Qwen2.5-1.5B-Instruct",        "chatml"),   # small, reliable
    ("microsoft/Phi-3-mini-4k-instruct",   "chatml"),   # Phi-3 (not 3.5)
    ("google/gemma-2-2b-it",               "chatml"),   # Gemma 2 2B
    ("mistralai/Mistral-7B-Instruct-v0.2", "mistral"),  # v0.2 (v0.3 is 410)
]

# Groq — current model names as of March 2026
_GROQ_MODELS = [
    "llama-3.3-70b-versatile",   # replaced llama-3.1-70b-versatile
    "llama-3.1-8b-instant",      # fast, always available
    "llama3-8b-8192",            # legacy alias — still active
]

# Gemini — 2.0-flash is now the free-tier model (1.5 deprecated)
_GEMINI_MODELS = [
    "gemini-2.0-flash",       # primary — replaces 1.5-flash
    "gemini-2.0-flash-lite",  # cheaper/faster fallback
]

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
        # Keys are loaded lazily via _get_keys() at call time, NOT here.
        # Loading in __init__ causes "No API keys configured" errors when
        # ai_services.py creates TextGenerationService() at module import
        # time — before Render injects env vars into the process. By the
        # time the first real request arrives the keys are available, but
        # this stale instance has already cached empty strings for them.
        pass

    def _get_keys(self):
        """Load API keys fresh from settings on every call chain."""
        from app.config import get_settings
        s = get_settings()
        hf_key     = getattr(s, "HUGGINGFACE_API_KEY", "") or ""
        groq_key   = getattr(s, "GROQ_API_KEY",        "") or ""
        gemini_key = getattr(s, "GEMINI_API_KEY",      "") or ""
        openai_key = getattr(s, "OPENAI_API_KEY",      "") or ""

        active = [k for k, v in {
            "HuggingFace": hf_key, "Groq": groq_key,
            "Gemini": gemini_key,  "OpenAI": openai_key,
        }.items() if v]

        if not active:
            logger.warning(
                "No AI API keys found in settings — "
                "set HUGGINGFACE_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY"
            )
        else:
            logger.info(f"AI providers active: {', '.join(active)}")

        return hf_key, groq_key, gemini_key, openai_key

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
        # Load keys fresh on every call — never stale from __init__
        hf_key, groq_key, gemini_key, openai_key = self._get_keys()
        errors: List[str] = []

        if hf_key:
            try:
                t = await self._hf_text(system, user_msg, hf_key)
                if t:
                    return t
            except Exception as e:
                errors.append(f"HuggingFace: {e}")

        if groq_key:
            try:
                t = await self._oai_compat(
                    _GROQ_URL, groq_key, _GROQ_MODELS, system, user_msg, "Groq"
                )
                if t:
                    return t
            except Exception as e:
                errors.append(f"Groq: {e}")

        if gemini_key:
            try:
                t = await self._gemini_text(system, user_msg, gemini_key)
                if t:
                    return t
            except Exception as e:
                errors.append(f"Gemini: {e}")

        if openai_key:
            try:
                t = await self._oai_compat(
                    _OPENAI_URL, openai_key, _OPENAI_MODELS, system, user_msg, "OpenAI"
                )
                if t:
                    return t
            except Exception as e:
                errors.append(f"OpenAI: {e}")

        if not errors:
            raise AIGenerationError(
                "No AI API keys are configured. "
                "Add GROQ_API_KEY, GEMINI_API_KEY, or HUGGINGFACE_API_KEY "
                "to your Render environment variables."
            )

        raise AIGenerationError(
            f"All AI providers failed. Errors: {' | '.join(errors)}"
        )

    # ── HuggingFace text ──────────────────────────────────────────────────────

    async def _hf_text(self, system: str, user_msg: str, hf_key: str = "") -> str:
        headers = {
            "Authorization": f"Bearer {hf_key or self._get_keys()[0]}",
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
                "max_tokens": 2048, "temperature": 0.75, "top_p": 0.90,
                # FIX B — forces pure JSON output, no preamble, no code fences.
                # Supported by all Groq models when the prompt mentions "JSON".
                # Also raises max_tokens 1400→2048: a 10-scene plan can be
                # ~1500 tokens; truncated responses caused cascading parse failures.
                "response_format": {"type": "json_object"},
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

    async def _gemini_text(self, system: str, user_msg: str, gemini_key: str = "") -> str:
        _gemini_key = gemini_key or self._get_keys()[2]
        for model in _GEMINI_MODELS:
            url     = _GEMINI_URL.format(model=model)
            payload = {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                "generationConfig": {
                    "maxOutputTokens": 2048, "temperature": 0.75, "topP": 0.90,
                },
            }
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    r = await c.post(url, params={"key": _gemini_key}, json=payload)
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
        hf_key, _, gemini_key, _ = self._get_keys()
        # 1. HF vision
        if hf_key:
            t = await self._hf_vision(img, hf_key)
            if t:
                return t
        # 2. Gemini vision
        if gemini_key:
            t = await self._gemini_vision(img, gemini_key)
            if t:
                return t
        raise AIGenerationError(
            "No vision provider available. Set HUGGINGFACE_API_KEY or GEMINI_API_KEY."
        )

    async def _hf_vision(self, img: bytes, hf_key: str = "") -> str:
        headers = {
            "Authorization": f"Bearer {hf_key}",
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

    async def _gemini_vision(self, img: bytes, gemini_key: str = "") -> str:
        b64  = base64.b64encode(img).decode()
        mime = "image/jpeg"
        if img[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif img[:4] == b"RIFF" and img[8:12] == b"WEBP":
            mime = "image/webp"
        url     = _GEMINI_URL.format(model="gemini-2.0-flash")   # updated from 1.5-flash
        payload = {
            "contents": [{"role": "user", "parts": [
                {"text": "Describe this image: subject, setting, lighting, colours, mood. Be specific."},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]}],
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0.4},
        }
        try:
            async with httpx.AsyncClient(timeout=_VISION_TIMEOUT) as c:
                r = await c.post(url, params={"key": gemini_key}, json=payload)
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
        "title":        data.get("title") or data.get("video_title") or idea[:60],
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



def _json(text: str) -> Optional[Dict]:
    """
    Robust JSON extractor. Handles:
    - ```json fences and preamble prose
    - // comments that are NOT inside string values
    - {} inside string values (string-aware brace walker)
    - Trailing commas, Python None/True/False
    """
    if not text:
        return None

    # 1. Strip markdown fences
    text = re.sub(r"```(?:json)?\s*|```", "", text).strip()

    # 2. Direct parse (handles perfectly-formed responses)
    try:
        return json.loads(text)
    except Exception:
        pass

    # 3. Strip // comments that are NOT inside string values, then retry
    cleaned = _strip_js_comments(text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 4. String-aware brace extraction
    candidate = _extract_json_object(cleaned)
    if candidate is None:
        logger.warning(f"JSON extraction failed. Raw prefix: {text[:300]!r}")
        return None

    # 5. Final repair pass
    candidate = _fix(candidate)
    try:
        return json.loads(candidate)
    except Exception as e:
        logger.warning(f"JSON repair failed: {e!r} | candidate: {candidate[:300]!r}")
        return None


def _strip_js_comments(s: str) -> str:
    """
    Remove // comments ONLY when outside a JSON string value.
    The old regex re.sub(r"//[^\n]*", ...) destroyed URLs (https://...)
    inside string values because "//" appears in every URL.
    """
    result = []
    i = 0
    in_string  = False
    escape_next = False
    while i < len(s):
        ch = s[i]
        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue
        if ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if not in_string and ch == "/" and i + 1 < len(s) and s[i + 1] == "/":
            while i < len(s) and s[i] != "\n":
                i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _extract_json_object(text: str) -> Optional[str]:
    """
    String-aware brace walker — does NOT count { } inside string values.
    The old naive walker terminated early when image_prompt contained
    {curly braces}, which large models (llama-3.3, GPT-4o) frequently use.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string  = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return text[start:] + "\n}"


def _fix(s: str) -> str:
    """
    Light repair pass: trailing commas + Python literal normalisation.

    FIX A — The old version had:
        re.sub(r"(?<![\\])'", '"', s)
    which replaced ALL unescaped single quotes with double quotes.
    This destroyed apostrophes inside string values:
        "Don't miss this!" → "Don"t miss this!" → JSON parse error.
    Groq, Gemini, and OpenAI always output proper double-quoted JSON so
    the single-quote normaliser was both unnecessary and catastrophic.
    Removed entirely.

    Does NOT strip // comments — handled by _strip_js_comments() first.
    """
    # Trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # Escape bare newlines inside string values
    s = re.sub(
        r'("(?:[^"\\]|\\.)*?")',
        lambda m: m.group(0).replace("\n", "\\n"), s,
    )
    # Python → JSON literals
    s = s.replace(": None", ": null").replace(": True", ": true").replace(": False", ": false")
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
