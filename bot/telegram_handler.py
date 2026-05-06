"""Telegram bot — full pipeline: link → MP3 → transcript → clips.json → cut MP4s.

Pipeline stages:
  1. Download audio (yt-dlp + Deno)
  2. Transcribe (Deepgram)
  3. Analyze for viral clips (Gemini)
  4. Download source video (yt-dlp 720p)
  5. Cut MP4 clips (FFmpeg) — 16:9 + naive 9:16
  6. Send clips to user via Telegram
  7. Auto-clean MP3 + MP4 + clips folder

Commands: /start, /help, /status, /clean, /cliponly (skip cutting, JSON only).
"""
import logging
import re
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TG_BOT_TOKEN, WORK_DIR
from worker.analyze import analyze_transcript, save_clips
from worker.cut import cleanup_clip_dir, cut_clips, total_size_mb
from worker.download import download_audio
from worker.download_video import download_video
from worker.transcribe import save_transcript, transcribe_audio

logger = logging.getLogger(__name__)

YT_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+"
)

# Telegram limits — Bot API caps documents at 50 MB. We keep clips well under that.
MAX_CLIPS_TO_SEND = 20  # send up to top-N highest-scored clips as files


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _delete_path_safely(path: Path | None) -> float:
    if not path or not path.exists():
        return 0.0
    size_mb = path.stat().st_size / 1024 / 1024
    try:
        path.unlink()
    except OSError as e:
        logger.warning("Failed to delete %s: %s", path, e)
        return 0.0
    return size_mb


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Send a YouTube podcast link.\n\n"
        "I'll: download → transcribe (Deepgram) → find viral clips (Gemini) → "
        "*cut actual MP4 clips* → send them back to you.\n\n"
        "Each clip ships in two formats:\n"
        "  • 16:9 for X / YouTube\n"
        "  • 9:16 for Reels / Shorts / TikTok\n\n"
        "Commands: /status /clean /cliponly /help",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Pipeline:* link → MP3 → Deepgram → Gemini → FFmpeg cuts → MP4 clips.\n\n"
        "Output: `transcript.txt`, `transcript.json`, `clips.json`, plus 16:9 + 9:16 MP4s.\n"
        "Audio + source video auto-deleted on success.\n\n"
        "*Commands:*\n"
        "/status — disk usage\n"
        "/clean — wipe cached audio/video\n"
        "/cliponly <YT URL> — skip cutting, just produce the JSON plan\n",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    audio_bytes = video_bytes = transcript_bytes = clip_bytes = 0
    audio_count = video_count = transcript_count = clip_count = 0
    for f in WORK_DIR.rglob("*"):
        if not f.is_file():
            continue
        size = f.stat().st_size
        if f.suffix == ".mp3":
            audio_count += 1
            audio_bytes += size
        elif f.suffix == ".mp4" and "_clip" not in f.name:
            video_count += 1
            video_bytes += size
        elif f.suffix == ".mp4":
            clip_count += 1
            clip_bytes += size
        elif f.suffix in (".json", ".txt"):
            transcript_count += 1
            transcript_bytes += size

    total_mb = (audio_bytes + video_bytes + transcript_bytes + clip_bytes) / 1024 / 1024
    await update.message.reply_text(
        f"💾 *Workdir disk usage*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📁 Total: {total_mb:.1f} MB\n"
        f"🎵 Audio cache: {audio_count}, {audio_bytes / 1024 / 1024:.1f} MB\n"
        f"🎞 Video cache: {video_count}, {video_bytes / 1024 / 1024:.1f} MB\n"
        f"📝 Transcripts/plans: {transcript_count}, {transcript_bytes / 1024 / 1024:.1f} MB\n"
        f"🎬 Cut clips: {clip_count}, {clip_bytes / 1024 / 1024:.1f} MB\n\n"
        f"/clean — wipe audio + video caches",
        parse_mode="Markdown",
    )


async def cmd_clean(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted_count = 0
    freed_bytes = 0
    for pattern in ("*.mp3", "*.mp4"):
        for f in WORK_DIR.glob(pattern):
            if "_clip" in f.name:
                continue  # don't touch already-cut clips
            try:
                freed_bytes += f.stat().st_size
                f.unlink()
                deleted_count += 1
            except OSError as e:
                logger.warning("Could not delete %s: %s", f, e)
    freed_mb = freed_bytes / 1024 / 1024
    if deleted_count == 0:
        msg = "🧹 Nothing to clean."
    else:
        msg = f"🧹 Deleted *{deleted_count}* file(s), freed *{freed_mb:.1f} MB*."
    await update.message.reply_text(msg, parse_mode="Markdown")


# ----------------------------------------------------------------------
# Main pipeline
# ----------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    cliponly = text.startswith("/cliponly")
    if cliponly:
        text = text.replace("/cliponly", "", 1).strip()

    match = YT_URL_RE.search(text)
    if not match:
        await update.message.reply_text(
            "Send a YouTube URL like https://www.youtube.com/watch?v=..."
        )
        return

    url = match.group(0)
    chat_id = update.effective_chat.id
    status_msg = await update.message.reply_text("⏳ Downloading audio...")

    audio_path: Path | None = None
    video_path: Path | None = None
    clips_out_dir: Path | None = None

    try:
        # === 1. Download audio ===
        audio_path, metadata = await download_audio(url, WORK_DIR)
        await status_msg.edit_text(
            f"✅ Got: *{metadata['title']}*\n"
            f"⏱ {metadata['duration_min']} min · {metadata['channel']}\n\n"
            f"⏳ Transcribing with Deepgram...",
            parse_mode="Markdown",
        )

        # === 2. Transcribe ===
        transcript = await transcribe_audio(audio_path)
        word_count = len(transcript.get("words", []))
        await status_msg.edit_text(
            f"✅ Transcribed: *{metadata['title']}* — {word_count} words\n\n"
            f"⏳ Finding viral clips with Gemini...",
            parse_mode="Markdown",
        )

        # === 3. Save transcript + analyze ===
        transcript_dir = WORK_DIR / metadata["video_id"]
        transcript_dir.mkdir(exist_ok=True)
        json_path = transcript_dir / "transcript.json"
        save_transcript(transcript, json_path)
        txt_path = json_path.with_suffix(".txt")

        clips_data = await analyze_transcript(transcript, metadata)
        clips = clips_data["clips"]
        clips_path = transcript_dir / "clips.json"
        save_clips(clips_data, clips_path)

        # Send transcript + plan files
        await context.bot.send_document(
            chat_id=chat_id,
            document=txt_path.open("rb"),
            filename=f"{metadata['video_id']}_transcript.txt",
            caption="📝 Transcript",
        )
        await context.bot.send_document(
            chat_id=chat_id,
            document=clips_path.open("rb"),
            filename=f"{metadata['video_id']}_clips.json",
            caption=f"🎬 Plan: {len(clips)} viral clips",
        )

        # /cliponly stops here
        if cliponly or not clips:
            freed_mb = _delete_path_safely(audio_path)
            await status_msg.edit_text(
                f"✅ *Done (plan only)*\n"
                f"📝 {word_count} words · 🎬 {len(clips)} clips planned\n"
                f"🧹 Freed {freed_mb:.1f} MB",
                parse_mode="Markdown",
            )
            return

        # === 4. Download source video for cutting ===
        await status_msg.edit_text(
            f"📋 Plan ready: *{len(clips)} clips*\n"
            f"⏳ Downloading source video for cutting...",
            parse_mode="Markdown",
        )
        video_path = await download_video(url, metadata["video_id"], WORK_DIR)

        # === 5. Cut clips ===
        clips_to_cut = clips[:MAX_CLIPS_TO_SEND]
        await status_msg.edit_text(
            f"🎞 Got source video ({video_path.stat().st_size / 1024 / 1024:.0f} MB)\n"
            f"⏳ Cutting {len(clips_to_cut)} clips with FFmpeg...",
            parse_mode="Markdown",
        )
        clips_out_dir = transcript_dir / "clips"
        results = await cut_clips(
            source_video=video_path,
            clips=clips_to_cut,
            out_dir=clips_out_dir,
            video_id=metadata["video_id"],
        )

        size_mb = total_size_mb(results)
        await status_msg.edit_text(
            f"✅ Cut {len(results)} clips ({size_mb:.0f} MB total)\n"
            f"⏳ Uploading to Telegram...",
            parse_mode="Markdown",
        )

        # === 6. Send each clip to user ===
        for r in results:
            clip = r["clip"]
            score = clip["virality_score"]
            hook = clip["hook"]
            duration = int(clip["duration"])
            start_t = _format_time(clip["start"])
            end_t = _format_time(clip["end"])
            caption_with_credit = f"{clip['caption']}\n\n🎙 {metadata['channel']}"

            header = (
                f"*[{score:.1f}/10]* {hook}\n"
                f"⏱ {start_t}–{end_t} ({duration}s)\n"
                f"💬 _{clip['caption']}_"
            )

            await context.bot.send_message(
                chat_id=chat_id,
                text=header,
                parse_mode="Markdown",
            )

            # 16:9 first (X-friendly), then 9:16 (Shorts/Reels)
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=r["path_16x9"].open("rb"),
                    filename=r["path_16x9"].name,
                    caption=f"📺 16:9 · post on X / YouTube\n\n{caption_with_credit}",
                    supports_streaming=True,
                )
            except Exception as e:
                logger.warning("16:9 send failed for clip %d: %s", r["index"], e)

            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=r["path_9x16"].open("rb"),
                    filename=r["path_9x16"].name,
                    caption=f"📱 9:16 · post on Reels / Shorts / TikTok\n\n{caption_with_credit}",
                    supports_streaming=True,
                )
            except Exception as e:
                logger.warning("9:16 send failed for clip %d: %s", r["index"], e)

        # === 7. Auto-cleanup ===
        freed = _delete_path_safely(audio_path)
        freed += _delete_path_safely(video_path)
        if clips_out_dir:
            freed += cleanup_clip_dir(clips_out_dir)

        await status_msg.edit_text(
            f"✅ *Done!* {metadata['title']}\n"
            f"🎬 {len(results)} clips delivered\n"
            f"🧹 Freed {freed:.0f} MB after upload",
            parse_mode="Markdown",
        )

    except Exception as exc:
        logger.exception("Pipeline failed for %s", url)
        await status_msg.edit_text(
            f"❌ Failed: `{exc}`\n\n"
            f"_Cached files kept for retry. Send link again to skip downloads._",
            parse_mode="Markdown",
        )


# ----------------------------------------------------------------------
# App builder
# ----------------------------------------------------------------------

def build_app() -> Application:
    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clean", cmd_clean))
    app.add_handler(CommandHandler("cliponly", handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
