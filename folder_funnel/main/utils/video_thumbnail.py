#region - Imports

# Standard
import hashlib
import os
import shutil
import subprocess
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app import Main


#endregion


#region - FFmpeg Detection


def find_ffmpeg() -> Optional[str]:
    """Return the full path to ffmpeg if available on PATH, else None."""
    try:
        path = shutil.which("ffmpeg")
        return path or None
    except Exception:
        return None


#endregion


#region - In-Memory Thumbnail Cache


def _thumb_key(
    video_path: str,
    mtime: float,
    size: int,
    width: int,
    timestamp_s: float,
    version: str = "v2",
) -> str:
    payload = f"{version}|{video_path}|{mtime}|{size}|{width}|{timestamp_s}".encode("utf-8", errors="ignore")
    return hashlib.md5(payload).hexdigest()


def _cache_get(app: 'Main', key: str) -> Optional[bytes]:
    cache = getattr(app, "_video_thumb_cache", None)
    if not isinstance(cache, dict):
        return None
    value = cache.get(key)
    return value if isinstance(value, (bytes, bytearray)) else None


def _cache_set(app: 'Main', key: str, value: bytes, max_items: int = 64) -> None:
    if not hasattr(app, "_video_thumb_cache") or not isinstance(getattr(app, "_video_thumb_cache"), dict):
        app._video_thumb_cache = {}
    if not hasattr(app, "_video_thumb_cache_order") or not isinstance(getattr(app, "_video_thumb_cache_order"), list):
        app._video_thumb_cache_order = []
    cache: dict = app._video_thumb_cache
    order: list = app._video_thumb_cache_order
    cache[key] = value
    order.append(key)
    # Trim oldest
    try:
        while len(order) > int(max_items):
            oldest = order.pop(0)
            cache.pop(oldest, None)
    except Exception:
        pass


#endregion


#region - Thumbnail Generation


def _ffmpeg_path(app: 'Main') -> Optional[str]:
    p = getattr(app, "ffmpeg_path", "")
    if p:
        return p
    return find_ffmpeg()


def _stat_key(video_path: str, width: int, timestamp_s: float) -> Optional[str]:
    try:
        st = os.stat(video_path)
        return _thumb_key(video_path, st.st_mtime, st.st_size, width, float(timestamp_s))
    except Exception:
        return None


def get_video_thumbnail_jpeg_bytes(
    app: 'Main',
    video_path: str,
    width: int = 400,
    timestamp_s: float = 1.0,
    timeout_s: float = 15.0,
) -> Optional[bytes]:
    """Return JPEG thumbnail bytes for a video file, cached in memory.

    Uses ffmpeg if available. Returns None on failure.
    """
    if not video_path or not os.path.isfile(video_path):
        return None
    ffmpeg = _ffmpeg_path(app)
    if not ffmpeg:
        return None
    key = _stat_key(video_path, width=width, timestamp_s=timestamp_s)
    if not key:
        return None
    cached = _cache_get(app, key)
    if cached:
        return bytes(cached)
    # Use a small offset so we don't commonly hit a black first frame.
    ts = max(0.0, float(timestamp_s))
    ts_str = f"{ts:.3f}"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        ts_str,
        "-i",
        video_path,
        "-an",
        "-sn",
        "-dn",
        "-frames:v",
        "1",
        "-vf",
        f"scale={int(width)}:-1",
        "-q:v",
        "2",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, timeout=timeout_s, creationflags=creationflags)
        data = proc.stdout or b""
    except Exception:
        return None
    # Basic sanity check: JPEG starts with 0xFFD8
    if not data or not data.startswith(b"\xff\xd8"):
        return None
    _cache_set(app, key, data)
    return data


#endregion
