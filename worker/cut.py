"""Cut clips from a source video using FFmpeg.

For each clip in clips.json, produces two outputs:
  - <id>_clipNN_16x9.mp4 — original aspect, ready for X timeline / YouTube
  - <id>_clipNN_9x16.mp4 — naive center-crop, for Reels / Shorts / TikTok

Smart speaker-aware cropping is M5. Burned-in subtitles are M4. This file is
intentionally simple: get usable clips out the door, then iterate quality.
"""
import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Output target dimensions
TARGET_HEIGHT_9X16 = 1920  # we'll match width to keep aspect (1080)
TARGET_WIDTH_9X16 = 1080


async def cut_clips(
    source_video: Path,
    clips: list[dict],
    out_dir: Path,
    video_id: str,
) -> list[dict]:
    """Cut all clips from source_video. Returns list of {clip, paths_16x9, paths_9x16}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for i, clip in enumerate(clips, 1):
        idx = f"{i:02d}"
        try:
            path_16 = out_dir / f"{video_id}_clip{idx}_16x9.mp4"
            path_9 = out_dir / f"{video_id}_clip{idx}_9x16.mp4"

            await _cut_16x9(source_video, clip, path_16)
            await _crop_9x16(path_16, path_9)

            results.append({
                "index": i,
                "clip": clip,
                "path_16x9": path_16,
                "path_9x16": path_9,
            })
            logger.info("Cut clip %d/%d: %s", i, len(clips), clip.get("hook", ""))
        except Exception as e:
            logger.exception("Failed to cut clip %d: %s", i, e)

    return results


async def _cut_16x9(source: Path, clip: dict, out: Path) -> None:
    """Cut the 16:9 segment using FFmpeg. Re-encodes for clean A/V sync."""
    start = float(clip["start"])
    duration = float(clip["end"]) - start

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}",
        "-i", str(source),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",  # web-streamable
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg cut failed: {stderr.decode()[:500]}")


async def _crop_9x16(src_16x9: Path, out_9x16: Path) -> None:
    """Naive center-crop from 16:9 → 9:16. Smart cropping is M5.

    The filter:
      1. Scale source so its HEIGHT matches target (1920), preserving aspect
      2. Center-crop horizontally to 1080 wide
    """
    vf = (
        f"scale=-2:{TARGET_HEIGHT_9X16},"
        f"crop={TARGET_WIDTH_9X16}:{TARGET_HEIGHT_9X16}"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src_16x9),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(out_9x16),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg crop failed: {stderr.decode()[:500]}")


def total_size_mb(results: list[dict]) -> float:
    total = 0
    for r in results:
        for k in ("path_16x9", "path_9x16"):
            p = r.get(k)
            if p and p.exists():
                total += p.stat().st_size
    return total / 1024 / 1024


def cleanup_clip_dir(out_dir: Path) -> float:
    """Delete the entire clips output directory. Returns MB freed."""
    if not out_dir.exists():
        return 0.0
    size = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
    shutil.rmtree(out_dir, ignore_errors=True)
    return size / 1024 / 1024
