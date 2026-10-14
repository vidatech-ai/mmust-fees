import io
import uuid

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from core.config import SUPABASE_SERVICE_KEY, SUPABASE_URL
from core.db import supabase
from core.security import current_student

router = APIRouter(prefix="/student", tags=["photo"])

BUCKET = "avatars"
MAX_BYTES = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse "decompression bomb" images

_BASE = SUPABASE_URL.rstrip("/")
_PUBLIC_PREFIX = f"{_BASE}/storage/v1/object/public/{BUCKET}/"
_AUTH = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "apikey": SUPABASE_SERVICE_KEY}


def _to_square_jpeg(raw: bytes) -> bytes:
    """Verify it is a real image, then rebuild it as a clean 400x400 JPEG."""
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise HTTPException(400, "Use a JPG, PNG or WebP picture")
        img = ImageOps.exif_transpose(img).convert("RGB")
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "That file is not a valid picture")
    img = ImageOps.fit(img, (400, 400), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)  # fresh file: metadata is gone
    return out.getvalue()


def _delete_old(url: str | None) -> None:
    """Best effort: remove the previous photo file. Never fails the request."""
    if not url or not url.startswith(_PUBLIC_PREFIX):
        return
    try:
        httpx.delete(f"{_BASE}/storage/v1/object/{BUCKET}/{url[len(_PUBLIC_PREFIX):]}", headers=_AUTH, timeout=15)
    except httpx.HTTPError:
        pass


def _current_url(student_id: str) -> str | None:
    rows = supabase.table("students").select("photo_url").eq("id", student_id).limit(1).execute().data
    return rows[0]["photo_url"] if rows else None


@router.post("/photo")
def upload_photo(file: UploadFile = File(...), student_id: str = Depends(current_student)):
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Picture is too large (max 5 MB)")
    if not raw:
        raise HTTPException(400, "No file received")

    data = _to_square_jpeg(raw)
    old_url = _current_url(student_id)

    # The path comes from the token's student id + a random name, never from the upload
    name = f"{student_id}/{uuid.uuid4().hex}.jpg"
    try:
        r = httpx.post(
            f"{_BASE}/storage/v1/object/{BUCKET}/{name}",
            headers={**_AUTH, "Content-Type": "image/jpeg"},
            content=data,
            timeout=30,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "Could not save the picture. Try again.")
    if r.status_code >= 300:
        raise HTTPException(502, "Could not save the picture. Try again.")

    url = _PUBLIC_PREFIX + name
    supabase.table("students").update({"photo_url": url}).eq("id", student_id).execute()
    _delete_old(old_url)
    return {"photo_url": url}


@router.delete("/photo")
def remove_photo(student_id: str = Depends(current_student)):
    old_url = _current_url(student_id)
    supabase.table("students").update({"photo_url": None}).eq("id", student_id).execute()
    _delete_old(old_url)
    return {"photo_url": None}
