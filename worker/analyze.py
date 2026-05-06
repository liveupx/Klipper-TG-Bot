"""Analyze a transcript with Gemini → return ranked viral clip ranges.

This is the most important file in the codebase. The viral-clip prompt
determines whether the whole product produces clips that actually go viral.
Iterate aggressively here based on what posts well on X.
"""
import asyncio
import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash-lite"
TARGET_CLIP_COUNT = 60   # ask Gemini for this many; user keeps top 40–50
MIN_CLIP_DURATION = 25   # seconds — anything shorter feels rushed
MAX_CLIP_DURATION = 130  # seconds — beyond this loses retention

VIRAL_CLIP_PROMPT_TEMPLATE = """\
You are an expert short-form video editor specializing in podcast clips that go viral on TikTok, Instagram Reels, YouTube Shorts, and X (Twitter). You have a track record of identifying clips that get millions of views.

# Task
Given the timestamped podcast transcript below, identify the {target_count} most viral-worthy moments.

# Podcast metadata
- Title: {title}
- Channel: {channel}
- Duration: {duration_min} minutes

# Hard requirements for each clip
- Duration: 30–120 seconds (sweet spot 60–90s)
- MUST start at a natural sentence boundary, never mid-thought
- MUST end with a punchline, conclusion, takeaway, or strong hook
- Self-contained: a viewer who never heard the rest of the podcast must understand it
- The first 3 seconds must hook the viewer (claim, question, surprising statement)

# Prioritize moments with these traits (in roughly this order)
1. Counter-intuitive claims, hot takes, contrarian ideas
2. Concrete stories with specific details (numbers, names, places, times)
3. Emotional peaks: laughter, surprise, anger, vulnerability, awe
4. Punchy aphorisms or one-liners that work as a quote on their own
5. Conflict, disagreement, or strong push-back between speakers
6. "Most people don't realize…", "The truth is…", "Here's what nobody tells you…" framings
7. Personal stakes: failures, regrets, near-misses, lessons learned the hard way
8. Practical, actionable advice with a clear "do this, not that" structure

# Avoid
- Filler intros, sponsor reads, "welcome back to the show"
- Setup talk: "can you hear me", "let me adjust", explaining what they'll discuss
- Vague generalities without specifics
- Rambling tangents that don't land
- Clips where you have to explain context to understand them

# Caption style
- Tweet body: 100–200 characters, hooky, ends with 1–2 hashtags
- Start with a hook: a question, a claim, "POV:", or a surprising fact
- Reference what's in the clip but don't fully spoil it — make people want to watch
- No emoji spam; max 1 relevant emoji
- DO NOT include channel credit in the caption — that's appended automatically downstream

# Virality score (0–10)
Use the FULL range. Most clips should be 5–7. Reserve:
- 9–10 for genuinely killer moments you'd bet money will hit a million views
- 8 for strong clips you'd post yourself
- 5–7 for solid filler clips
- below 5 for borderline / risky clips that might still work

# Output format
Return ONLY a valid JSON object matching this exact schema. No markdown fences, no commentary, no leading text. Just the JSON.

{{
  "clips": [
    {{
      "start": 123.4,
      "end": 187.2,
      "hook": "Why most people fail",
      "caption": "Most people don't fail because they lack talent. They fail because they confuse motion with progress. 🔥 #productivity #mindset",
      "virality_score": 8.5,
      "reason": "Counter-intuitive claim with a quotable framing; lands in under 60s",
      "topic": "self-discipline"
    }}
  ]
}}

# Field rules
- start, end: floats in seconds, taken from the transcript timestamps. Snap to nearest sentence boundary.
- hook: 4–8 words, under 60 chars total, no quotes, title case
- caption: 100–200 chars including hashtags
- virality_score: float 0.0–10.0, one decimal place
- reason: one short sentence, what makes this clip work
- topic: 1–3 words, kebab-case if multi-word

# Transcript (with [HH:MM:SS] timestamps per segment)
{transcript_block}
"""


async def analyze_transcript(transcript: dict, metadata: dict) -> dict:
    """Run Gemini on a transcript and return clip ranges.

    Returns the raw Gemini JSON response, augmented with a `metadata` block.
    """
    transcript_block = _format_transcript(transcript)
    prompt = VIRAL_CLIP_PROMPT_TEMPLATE.format(
        target_count=TARGET_CLIP_COUNT,
        title=metadata.get("title", "Untitled"),
        channel=metadata.get("channel", "Unknown"),
        duration_min=metadata.get("duration_min", "?"),
        transcript_block=transcript_block,
    )

    prompt_chars = len(prompt)
    logger.info(
        "Analyzing transcript with Gemini (%s) — prompt: %d chars (~%dk tokens)",
        GEMINI_MODEL, prompt_chars, prompt_chars // 4 // 1000,
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    def _call():
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,  # some creativity for hook variety
                max_output_tokens=16384,
            ),
        )

    response = await asyncio.to_thread(_call)
    raw_text = response.text or ""
    parsed = _parse_response(raw_text)

    # Filter + sanitize
    clips = _sanitize_clips(parsed.get("clips", []), metadata)
    clips.sort(key=lambda c: c["virality_score"], reverse=True)

    logger.info("Gemini returned %d clips", len(clips))
    if clips:
        scores = [c["virality_score"] for c in clips]
        logger.info(
            "Score range: %.1f – %.1f (median %.1f)",
            min(scores), max(scores), sorted(scores)[len(scores) // 2],
        )

    return {
        "metadata": {
            "video_id": metadata.get("video_id"),
            "title": metadata.get("title"),
            "channel": metadata.get("channel"),
            "duration_min": metadata.get("duration_min"),
            "url": metadata.get("url"),
            "model": GEMINI_MODEL,
            "clip_count": len(clips),
        },
        "clips": clips,
    }


def _format_transcript(transcript: dict) -> str:
    """Convert segments to '[HH:MM:SS] text' lines for the prompt."""
    segments = transcript.get("segments") or []
    if not segments:
        # Fallback: use raw text without timestamps (Gemini will guess times poorly)
        return transcript.get("text", "")

    lines = []
    for seg in segments:
        ts = _seconds_to_hms(seg["start"])
        text = seg["text"].strip()
        if text:
            lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


def _seconds_to_hms(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_response(raw_text: str) -> dict[str, Any]:
    """Parse Gemini's JSON response, tolerating accidental markdown fences."""
    text = raw_text.strip()
    # Strip code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Gemini returned non-JSON. First 500 chars:\n%s", text[:500])
        raise ValueError(f"Could not parse Gemini response as JSON: {e}") from e


def _sanitize_clips(raw_clips: list, metadata: dict) -> list[dict]:
    """Drop malformed clips, clamp durations, augment with derived fields."""
    duration_sec = metadata.get("duration_sec", 0) or 0
    sane = []
    for c in raw_clips:
        try:
            start = float(c["start"])
            end = float(c["end"])
            duration = end - start
            if duration < MIN_CLIP_DURATION or duration > MAX_CLIP_DURATION:
                continue
            if start < 0 or (duration_sec > 0 and end > duration_sec + 5):
                continue
            sane.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(duration, 2),
                "hook": str(c.get("hook", "")).strip()[:80],
                "caption": str(c.get("caption", "")).strip()[:280],
                "virality_score": float(c.get("virality_score", 5.0)),
                "reason": str(c.get("reason", "")).strip()[:200],
                "topic": str(c.get("topic", "")).strip()[:40],
            })
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Dropped malformed clip: %s (%s)", c, e)
            continue
    return sane


def save_clips(clips_data: dict, out_path) -> None:
    """Save clips JSON to disk."""
    out_path.write_text(json.dumps(clips_data, ensure_ascii=False, indent=2))
