"""Download audio from YouTube as Whisper-optimized MP3.

Uses yt-dlp + FFmpeg postprocessing. Outputs 16kHz mono 64kbps MP3.

Resilience features:
- Browser cookies (COOKIES_FROM_BROWSER) bypass YouTube bot detection.
- Multi-client extraction (ios, web, android) bypasses format-restriction errors.
- Cached MP3s skip re-download.
"""
import asyncio
import logging
from pathlib import Path

import yt_dlp

from config import (
    AUDIO_BITRATE,
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    COOKIES_FILE,
    COOKIES_FROM_BROWSER,
)

logger = logging.getLogger(__name__)


def _build_metadata(info: dict, url: str) -> dict:
    duration_sec = info.get("duration", 0) or 0
    return {
        "video_id": info["id"],
        "title": info.get("title", "Untitled"),
        "channel": info.get("uploader") or info.get("channel", "Unknown"),
        "duration_sec": duration_sec,
        "duration_min": round(duration_sec / 60, 1),
        "url": url,
    }


def _common_opts() -> dict:
    """yt-dlp options shared between metadata extraction and full download.

    Try multiple player clients in order — ios first because YouTube serves
    full audio formats to it most reliably as of mid-2026.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "web", "android", "tv_embedded"],
            }
        },
    }
    if COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER,)
    elif COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE
    return opts


async def download_audio(url: str, work_dir: Path) -> tuple[Path, dict]:
    """Download audio from YouTube. Returns (audio_path, metadata)."""
    work_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: cheap metadata extract (no download) to get video ID
    def _extract_meta():
        # For metadata-only, skip the format check to avoid spurious errors
        meta_opts = {**_common_opts(), "skip_download": True}
        with yt_dlp.YoutubeDL(meta_opts) as ydl:
            return ydl.extract_info(url, download=False, process=False)

    logger.info("Resolving metadata for: %s", url)
    info = await asyncio.to_thread(_extract_meta)
    expected_path = work_dir / f"{info['id']}.mp3"
    metadata = _build_metadata(info, url)

    # Step 2: skip download if MP3 already cached
    if expected_path.exists():
        size_mb = expected_path.stat().st_size / 1024 / 1024
        logger.info(
            "✓ Cached audio found: %s (%.1f MB) — skipping download",
            expected_path.name, size_mb,
        )
        return expected_path, metadata

    # Step 3: real download + FFmpeg postprocess
    logger.info(
        "Downloading audio: %s (%s min) from %s",
        metadata["title"], metadata["duration_min"], metadata["channel"],
    )

    # Permissive format selector — try multiple paths from cleanest to fallback
    fmt = "bestaudio[ext=m4a]/bestaudio/best[height<=720]/best"

    ydl_opts = {
        **_common_opts(),
        "format": fmt,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": AUDIO_BITRATE.rstrip("k"),
        }],
        "postprocessor_args": [
            "-ac", str(AUDIO_CHANNELS),
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-b:a", AUDIO_BITRATE,
        ],
        "outtmpl": str(work_dir / "%(id)s.%(ext)s"),
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = await asyncio.to_thread(_download)

    if not expected_path.exists():
        raise FileNotFoundError(f"Expected audio at {expected_path} but it's not there")

    metadata = _build_metadata(info, url)
    logger.info(
        "Downloaded: %s (%s min) from %s",
        metadata["title"], metadata["duration_min"], metadata["channel"],
    )
    return expected_path, metadata
