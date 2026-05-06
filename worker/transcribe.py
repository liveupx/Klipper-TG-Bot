"""Transcribe audio with Deepgram Nova-3.

Returns word-level timestamps for subtitle generation. No chunking needed —
Deepgram handles files of any size in a single call. No rate limits at our
scale ($200 free credit ≈ 775 hours of audio).
"""
import asyncio
import json
import logging
from pathlib import Path

import httpx

from config import DEEPGRAM_API_KEY

logger = logging.getLogger(__name__)

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_MODEL = "nova-3"


async def transcribe_audio(audio_path: Path) -> dict:
    """Transcribe an audio file with Deepgram.

    Returns: {"text": str, "words": [{word, start, end}], "segments": [...]}
    """
    size_mb = audio_path.stat().st_size / 1024 / 1024
    logger.info("Transcribing with Deepgram: %s (%.1f MB)", audio_path.name, size_mb)

    params = {
        "model": DEEPGRAM_MODEL,
        "punctuate": "true",
        "smart_format": "true",
        "utterances": "true",
        "language": "multi",  # auto-detect, handles Hindi/English code-switching
    }
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/mpeg",
    }

    audio_bytes = audio_path.read_bytes()

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            DEEPGRAM_URL,
            params=params,
            headers=headers,
            content=audio_bytes,
        )
        response.raise_for_status()
        data = response.json()

    return _parse_response(data)


def _parse_response(data: dict) -> dict:
    """Convert Deepgram's response to our internal format."""
    results = data.get("results", {})
    channels = results.get("channels", [])
    if not channels:
        raise ValueError("Deepgram returned no channels")

    alt = channels[0]["alternatives"][0]
    full_text = alt.get("transcript", "")

    words = [
        {
            "word": w.get("punctuated_word") or w["word"],
            "start": w["start"],
            "end": w["end"],
        }
        for w in alt.get("words", [])
    ]

    # Deepgram's "utterances" are our "segments" — natural sentence/phrase chunks
    utterances = results.get("utterances", [])
    segments = [
        {
            "text": u["transcript"],
            "start": u["start"],
            "end": u["end"],
        }
        for u in utterances
    ]

    # Fallback: if utterances aren't present, derive segments from words by gap
    if not segments and words:
        current = {"text": "", "start": words[0]["start"], "end": words[0]["end"]}
        for w in words:
            if w["start"] - current["end"] > 0.8:  # >0.8s pause = new segment
                segments.append(current)
                current = {"text": "", "start": w["start"], "end": w["end"]}
            current["text"] = (current["text"] + " " + w["word"]).strip()
            current["end"] = w["end"]
        segments.append(current)

    return {"text": full_text, "words": words, "segments": segments}


def save_transcript(transcript: dict, out_path: Path) -> Path:
    """Save full transcript JSON. Also writes a .txt next to it with just the text."""
    out_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2))
    txt_path = out_path.with_suffix(".txt")
    txt_path.write_text(transcript["text"])
    return out_path
