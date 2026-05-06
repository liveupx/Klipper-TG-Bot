"""Download the source video file from YouTube (mp4, 720p capped).

Used by the clipper. Audio-only download lives in download.py — this is the
companion that gets the picture.
"""
import asyncio
import logging
from pathlib import Path

import yt_dlp

from config import COOKIES_FILE, COOKIES_FROM_BROWSER

logger = logging.getLogger(__name__)


def _common_opts() -> dict:
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


async def download_video(url: str, video_id: str, work_dir: Path) -> Path:
    """Download the video as MP4 (720p max for speed + storage).

    Caches by video_id — if `<work_dir>/<id>.mp4` exists, returns it without
    re-downloading. Returns the Path to the MP4.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    expected_path = work_dir / f"{video_id}.mp4"

    if expected_path.exists():
        size_mb = expected_path.stat().st_size / 1024 / 1024
        logger.info(
            "✓ Cached video found: %s (%.1f MB) — skipping download",
            expected_path.name, size_mb,
        )
        return expected_path

    logger.info("Downloading video for clipping: %s", url)

    # Cap at 720p — clips on phones don't need 1080p+, and storage matters
    fmt = (
        "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/"
        "best[ext=mp4][height<=720]/"
        "best[height<=720]/"
        "best"
    )

    ydl_opts = {
        **_common_opts(),
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": str(work_dir / f"{video_id}.%(ext)s"),
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    await asyncio.to_thread(_download)

    if not expected_path.exists():
        # yt-dlp sometimes writes .mkv when merge fails; find any video file
        for cand in work_dir.glob(f"{video_id}.*"):
            if cand.suffix in (".mp4", ".mkv", ".webm"):
                logger.warning("Merged file at %s; renaming to .mp4", cand)
                cand.rename(expected_path)
                break

    if not expected_path.exists():
        raise FileNotFoundError(f"Video download failed for {video_id}")

    size_mb = expected_path.stat().st_size / 1024 / 1024
    logger.info("Downloaded %s (%.1f MB)", expected_path.name, size_mb)
    return expected_path
