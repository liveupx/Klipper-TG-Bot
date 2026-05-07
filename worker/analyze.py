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
MIN_CLIPS_FORCED = 5     # always return at least this many, even from "weak" content
MIN_CLIP_DURATION = 20   # seconds — was 25; loosened to catch punchy short moments
MAX_CLIP_DURATION = 130  # seconds — beyond this loses retention

VIRAL_CLIP_PROMPT_TEMPLATE = """\
You are an expert short-form video editor specializing in podcast and interview clips that perform well on TikTok, Instagram Reels, YouTube Shorts, and X (Twitter). You have a track record of identifying clips that get high engagement.

# Task
Given the timestamped transcript below, identify up to {target_count} clip-worthy moments. AT MINIMUM you MUST return {min_clips} clips, even if you think the content is "boring" — your job is to find the best clip-worthy moments that exist, not to gatekeep on perfection.

# Podcast metadata
- Title: {title}
- Channel: {channel}
- Duration: {duration_min} minutes

# Hard requirements for each clip
- Duration: 20–120 seconds (sweet spot 45–90s)
- MUST start at a natural sentence boundary, never mid-thought
- MUST end with a complete thought — a statement, conclusion, takeaway, or quote that "lands"
- Self-contained: a viewer who never heard the rest must understand it
- The opening line should be interesting on its own — a claim, a question, a surprising fact, a story setup, or a strong opinion

# What makes a clip work — broaden your aperture
This is NOT just "hot takes and one-liners." Clips can succeed on multiple dimensions:

**HIGH viral potential (score 7–10):**
- Counter-intuitive claims and hot takes
- Punchy one-liners and aphorisms
- Emotional peaks (surprise, anger, vulnerability, awe, laughter)
- Concrete stories with specific details (numbers, names, places)
- Conflict, disagreement, or strong push-back
- "Most people don't realize…", "The truth is…" framings

**SOLID clip-worthy (score 5–7):**
- Thoughtful expert insights and analysis
- Clear explanations of complex ideas
- Predictions, warnings, or forward-looking statements
- Personal experiences and "what I learned" moments
- Behind-the-scenes details and insider perspectives
- Clear "do this, not that" actionable advice
- Articulate framings of important questions
- Direct answers to questions the audience cares about

**Always include if found (even with no obvious "hook"):**
- The most quotable line in the entire interview
- The interviewee's strongest argument
- A moment where they say something unexpected for someone in their position
- The clearest articulation of why this topic matters

# Avoid
- Filler intros, sponsor reads, "welcome back to the show"
- Setup talk: "let me adjust my mic", "as I was saying earlier"
- Vague generalities with zero specifics
- Clips where you'd need extensive context to follow

# Caption style
- Tweet body: 100–200 characters, hooky, ends with 1–2 hashtags
- Start with a hook: a question, a claim, "POV:", or a surprising fact
- Reference what's in the clip but don't fully spoil it — make people want to watch
- No emoji spam; max 1 relevant emoji
- DO NOT include channel credit in the caption — that's appended automatically downstream

# Virality score (0–10) — USE THE FULL RANGE
Most clips should be 5–7. Reserve:
- 9–10 for genuinely killer moments you'd bet money on going viral
- 8 for strong clips you'd post yourself today
- 6–7 for solid filler clips with a clear hook
- 4–5 for borderline clips that work in context but lack a punch
- below 4 only for the worst inclusion in your top set

For "measured" content (news interviews, policy talks, technical discussions), DO NOT artificially boost scores — but DO include enough clips to give the user material to choose from. A score of 5 is still publishable.

# Output format
Return ONLY a valid JSON object matching this exact structure. No markdown fences, no commentary, no leading text. Just the JSON.

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
- reason: one short sentence on why this clip works
- topic: 1–3 words, kebab-case if multi-word

# Final reminder
You MUST return at least {min_clips} clips. If the content is challenging (a measured policy interview, a technical talk, a low-energy conversation), find the most clip-worthy moments anyway and score them honestly (a 5 is fine). Returning fewer than {min_clips} is failure. Returning a thoughtful set scored honestly is success.

# Transcript (with [HH:MM:SS] timestamps per segment)
{transcript_block}
"""


async def analyze_transcript(transcript: dict, metadata: dict) -> dict:
    """Run Gemini on a transcript and return clip ranges."""
    transcript_block = _format_transcript(transcript)
    prompt = VIRAL_CLIP_PROMPT_TEMPLATE.format(
        target_count=TARGET_CLIP_COUNT,
        min_clips=MIN_CLIPS_FORCED,
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
                temperature=0.7,
                max_output_tokens=16384,
            ),
        )

    response = await asyncio.to_thread(_call)
    raw_text = response.text or ""
    parsed = _parse_response(raw_text)

    # Filter + sanitize
    raw_count = len(parsed.get("clips", []))
    clips = _sanitize_clips(parsed.get("clips", []), metadata)
    clips.sort(key=lambda c: c["virality_score"], reverse=True)

    if raw_count != len(clips):
        logger.warning(
            "Sanitize dropped %d clips (Gemini gave %d, kept %d). Check duration/timestamps.",
            raw_count - len(clips), raw_count, len(clips),
        )

    logger.info("Gemini returned %d clips (post-sanitize)", len(clips))
    if clips:
        scores = [c["virality_score"] for c in clips]
        logger.info(
            "Score range: %.1f – %.1f (median %.1f)",
            min(scores), max(scores), sorted(scores)[len(scores) // 2],
        )
    else:
        logger.error(
            "Gemini returned 0 clips for %s. Raw response (first 500 chars):\n%s",
            metadata.get("video_id"), raw_text[:500],
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
    dropped_reasons = {"duration": 0, "bounds": 0, "malformed": 0}

    for c in raw_clips:
        try:
            start = float(c["start"])
            end = float(c["end"])
            duration = end - start
            if duration < MIN_CLIP_DURATION or duration > MAX_CLIP_DURATION:
                dropped_reasons["duration"] += 1
                continue
            if start < 0 or (duration_sec > 0 and end > duration_sec + 5):
                dropped_reasons["bounds"] += 1
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
            dropped_reasons["malformed"] += 1
            logger.warning("Dropped malformed clip: %s (%s)", c, e)
            continue

    if any(dropped_reasons.values()):
        logger.info("Sanitize drops: %s", dropped_reasons)
    return sane


def save_clips(clips_data: dict, out_path) -> None:
    """Save clips JSON to disk."""
    out_path.write_text(json.dumps(clips_data, ensure_ascii=False, indent=2))
