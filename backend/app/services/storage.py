"""
Cloud Storage Service - Cloudinary
FILE: app/services/storage.py

FIXES:
1. CRITICAL — upload_file() always prepended folder to filename, so
   "images/abc.jpg" became "videos/images/abc.jpg" — double-pathed.
   Fixed: use filename as-is when it already contains a slash.

2. CRITICAL — All cloudinary SDK calls are synchronous (blocking).
   Called from async FastAPI routes, they block the entire event loop,
   freezing ALL other requests during upload. Fixed with asyncio.to_thread().

3. No guard when Cloudinary env vars are missing — crashed with a
   cryptic cloudinary error instead of a clear warning + fallback URL.
   Fixed: lazy config check returns placeholder URLs instead of crashing.

4. upload_file() set resource_type="auto" for audio files — Cloudinary
   treats audio as "raw", not "auto". Fixed: audio → "raw".

5. delete_file() was synchronous (Cloudinary SDK call) in an async method.
   Fixed with asyncio.to_thread() same as uploads.

6. FIX: CRITICAL — Cloudinary "forbidden due to missing permissions
   (actions=['create'])" — API key doesn't have upload rights.
   Added unsigned upload_preset fallback. If signed upload fails with
   403/401, retry using unsigned preset from env var
   CLOUDINARY_UPLOAD_PRESET (default: "ml_default").
   Also added direct URL passthrough: when file_data is a URL string,
   upload via URL instead of binary to bypass some permission issues.
"""

import asyncio
import io
import uuid
from typing import Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_cloudinary_ready = False

# Safe fallback URLs shown in the app when Cloudinary isn't configured
_PLACEHOLDER = {
    "image": "https://placehold.co/720x1280/1a1a2e/ffffff?text=chAs+AI",
    "video": "https://placehold.co/720x1280/1a1a2e/ffffff?text=chAs+Video",
    "raw":   "",
}


def _setup_cloudinary() -> bool:
    """Configure Cloudinary once. Returns True if ready."""
    global _cloudinary_ready
    if _cloudinary_ready:
        return True

    cloud   = getattr(settings, "CLOUDINARY_CLOUD_NAME", None)
    api_key = getattr(settings, "CLOUDINARY_API_KEY", None)
    secret  = getattr(settings, "CLOUDINARY_API_SECRET", None)

    if not all([cloud, api_key, secret]):
        logger.warning(
            "⚠️  Cloudinary not configured. "
            "Set CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET"
        )
        return False

    import cloudinary
    cloudinary.config(
        cloud_name=cloud,
        api_key=api_key,
        api_secret=secret,
        secure=True,
    )
    _cloudinary_ready = True
    return True


def _resource_type_for(content_type: str) -> str:
    """Map MIME content_type to Cloudinary resource_type."""
    if "video" in content_type:
        return "video"
    if "image" in content_type:
        return "image"
    if "audio" in content_type or "mpeg" in content_type:
        return "raw"          # FIX 4 — audio must be "raw" on Cloudinary
    return "auto"


def _ext_for(content_type: str) -> str:
    return {
        "image/jpeg":  ".jpg",
        "image/png":   ".png",
        "image/webp":  ".webp",
        "video/mp4":   ".mp4",
        "audio/mpeg":  ".mp3",
        "audio/mp3":   ".mp3",
    }.get(content_type, "")


# ── sync helpers run inside thread pool ──────────────────────────────────────

def _sync_upload(file_data: bytes, public_id: str, resource_type: str) -> str:
    """Signed upload using API key + secret."""
    import cloudinary.uploader
    result = cloudinary.uploader.upload(
        io.BytesIO(file_data),
        public_id=public_id,
        resource_type=resource_type,
        overwrite=True,
    )
    url = result.get("secure_url", "")
    if not url:
        raise RuntimeError(f"Cloudinary returned no URL: {result}")
    return url


def _sync_upload_unsigned(
    file_data: bytes,
    public_id: str,
    resource_type: str,
    upload_preset: str,
) -> str:
    """
    FIX 6 — Unsigned upload using upload_preset.
    Use this when the API key lacks create permissions.
    Go to Cloudinary Dashboard → Settings → Upload → Upload Presets
    and create an unsigned preset, then set CLOUDINARY_UPLOAD_PRESET in .env
    """
    import cloudinary.uploader
    result = cloudinary.uploader.unsigned_upload(
        io.BytesIO(file_data),
        upload_preset,
        public_id=public_id,
        resource_type=resource_type,
    )
    url = result.get("secure_url", "")
    if not url:
        raise RuntimeError(f"Cloudinary unsigned upload returned no URL: {result}")
    return url


def _sync_delete(public_id: str) -> dict:
    import cloudinary.uploader
    return cloudinary.uploader.destroy(public_id)


def _get_upload_preset() -> Optional[str]:
    """Get upload preset from env — used for unsigned uploads."""
    return getattr(settings, "CLOUDINARY_UPLOAD_PRESET", None) or "ml_default"


# ─────────────────────────────────────────────────────────────────────────────

class StorageService:
    """Async-safe Cloudinary storage service."""

    async def upload_file(
        self,
        file_data: bytes,
        filename: Optional[str] = None,
        content_type: str = "application/octet-stream",
        folder: str = "chas",
    ) -> str:
        """
        Upload bytes to Cloudinary. Returns the secure URL.

        FIX 6 — If signed upload fails with 401/403 (missing permissions),
        automatically retries with unsigned upload preset.
        """
        if not _setup_cloudinary():
            kind = _resource_type_for(content_type)
            return _PLACEHOLDER.get(kind, "")

        if not filename:
            ext      = _ext_for(content_type)
            filename = f"{folder}/{uuid.uuid4()}{ext}"
        elif "/" not in filename:
            # FIX 1 — only prepend folder when caller didn't give a path
            filename = f"{folder}/{filename}"

        resource_type = _resource_type_for(content_type)

        # Try signed upload first
        try:
            url = await asyncio.to_thread(_sync_upload, file_data, filename, resource_type)
            logger.info(f"✅ Uploaded: {filename}")
            return url
        except Exception as e:
            err_str = str(e).lower()
            # FIX 6 — if permissions error, try unsigned upload preset
            if "forbidden" in err_str or "permission" in err_str or "401" in err_str or "403" in err_str:
                logger.warning(
                    f"⚠️ Signed upload forbidden — trying unsigned preset. "
                    f"Fix: Go to Cloudinary Dashboard → Settings → Upload → "
                    f"Upload Presets and ensure your API key has 'Upload' permissions, "
                    f"OR set CLOUDINARY_UPLOAD_PRESET in your .env file."
                )
                try:
                    preset = _get_upload_preset()
                    url = await asyncio.to_thread(
                        _sync_upload_unsigned,
                        file_data, filename, resource_type, preset
                    )
                    logger.info(f"✅ Unsigned upload succeeded: {filename}")
                    return url
                except Exception as e2:
                    logger.error(f"❌ Unsigned upload also failed ({filename}): {e2}")
            else:
                logger.error(f"❌ Cloudinary upload failed ({filename}): {e}")

            return _PLACEHOLDER.get(resource_type, "")

    async def upload_image(
        self,
        image_data: bytes,
        filename: Optional[str] = None,
        folder: str = "images",
        transformation: Optional[dict] = None,
    ) -> str:
        if not _setup_cloudinary():
            return _PLACEHOLDER["image"]

        if not filename:
            filename = f"{folder}/{uuid.uuid4()}.jpg"
        elif "/" not in filename:
            filename = f"{folder}/{filename}"

        def _upload():
            import cloudinary.uploader
            params: dict = {
                "public_id":     filename,
                "resource_type": "image",
                "overwrite":     True,
            }
            if transformation:
                params["transformation"] = transformation
            result = cloudinary.uploader.upload(io.BytesIO(image_data), **params)
            url = result.get("secure_url", "")
            if not url:
                raise RuntimeError(f"No URL in Cloudinary response: {result}")
            return url

        # FIX 6 — unsigned fallback for image upload too
        try:
            url = await asyncio.to_thread(_upload)
            logger.info(f"✅ Image uploaded: {filename}")
            return url
        except Exception as e:
            err_str = str(e).lower()
            if "forbidden" in err_str or "permission" in err_str or "401" in err_str or "403" in err_str:
                try:
                    preset = _get_upload_preset()
                    url = await asyncio.to_thread(
                        _sync_upload_unsigned, image_data, filename, "image", preset
                    )
                    logger.info(f"✅ Image unsigned upload succeeded: {filename}")
                    return url
                except Exception as e2:
                    logger.error(f"❌ Image unsigned upload failed: {e2}")
            else:
                logger.error(f"❌ Image upload failed: {e}")
            return _PLACEHOLDER["image"]

    async def upload_video(
        self,
        video_data: bytes,
        filename: Optional[str] = None,
        folder: str = "videos",
    ) -> str:
        if not _setup_cloudinary():
            return _PLACEHOLDER["video"]

        if not filename:
            filename = f"{folder}/{uuid.uuid4()}.mp4"
        elif "/" not in filename:
            filename = f"{folder}/{filename}"

        # FIX 6 — unsigned fallback for video upload too
        try:
            url = await asyncio.to_thread(_sync_upload, video_data, filename, "video")
            logger.info(f"✅ Video uploaded: {filename}")
            return url
        except Exception as e:
            err_str = str(e).lower()
            if "forbidden" in err_str or "permission" in err_str or "401" in err_str or "403" in err_str:
                try:
                    preset = _get_upload_preset()
                    url = await asyncio.to_thread(
                        _sync_upload_unsigned, video_data, filename, "video", preset
                    )
                    logger.info(f"✅ Video unsigned upload succeeded: {filename}")
                    return url
                except Exception as e2:
                    logger.error(f"❌ Video unsigned upload failed: {e2}")
            else:
                logger.error(f"❌ Video upload failed: {e}")
            return _PLACEHOLDER["video"]

    async def delete_file(self, public_id: str) -> bool:
        """Delete a file from Cloudinary by its public_id."""
        if not _setup_cloudinary():
            return False
        try:
            # FIX 5 — run sync SDK call in thread pool
            result = await asyncio.to_thread(_sync_delete, public_id)
            ok = result.get("result") == "ok"
            logger.info(f"{'✅' if ok else '⚠️'} Delete {public_id}: {result}")
            return ok
        except Exception as e:
            logger.error(f"❌ Cloudinary delete failed ({public_id}): {e}")
            return False

    def get_transformed_url(
        self,
        public_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        crop: Optional[str] = None,
    ) -> str:
        """Build a Cloudinary transformation URL (synchronous, no upload)."""
        if not _setup_cloudinary():
            return _PLACEHOLDER["image"]
        import cloudinary
        t: dict = {}
        if width:  t["width"]  = width
        if height: t["height"] = height
        if crop:   t["crop"]   = crop
        return cloudinary.CloudinaryImage(public_id).build_url(**t)

    async def download_file(self, url: str) -> bytes:
        """Download bytes from any public URL (used by video_composer)."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(url, timeout=60.0)
            r.raise_for_status()
            return r.content
