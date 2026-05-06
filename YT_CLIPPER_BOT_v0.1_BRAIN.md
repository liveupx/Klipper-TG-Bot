# YT Clipper Bot — Project Brain

**Created:** 2026-05-06
**Last Updated:** 2026-05-06
**Version:** v0.1 (planning phase)

---

## 🧠 Resume Instructions (READ FIRST)

You are picking up an in-progress project. Before responding to anything:

1. Read this entire file end-to-end — every section.
2. Confirm understanding back to the user in 2–3 lines (what we're building, current phase, immediate next step).
3. Ask what they want to tackle next.

Do **not** suggest paid services, Twitter/X API, or non-AWS infra unless the user raises it — those are explicitly deferred (see §10).

---

## 1. Project Snapshot

A **Telegram bot** that takes one or more YouTube podcast links as input and returns **40–50 viral short clips per podcast** in both **9:16** (Reels/Shorts/TikTok) and **16:9** (X/YouTube) formats, each with **burned-in styled subtitles** and an **AI-generated caption + credit line**.

The user posts clips manually to **X.com (Twitter)** to grow followers, get monetized, and earn from posting. Automated posting is explicitly **deferred** until the clip pipeline produces consistently viral output.

**Current phase:** Planning complete → starting Week 1 build (Telegram bot + download + transcription).

---

## 2. Tech Stack & Environment

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | Best ecosystem for ML/video/bot work |
| Bot framework | **python-telegram-bot v21+** | Most mature, async support |
| Video download | **yt-dlp** (latest) | Active fork, handles YT changes |
| Transcription | **Groq API — `whisper-large-v3-turbo`** | Free, ~200x realtime, word-level timestamps |
| Clip selection LLM | **Gemini 2.0 Flash** (free tier: 15 RPM, 1M tokens/day) | Long context handles full transcripts in one shot |
| Backup LLM | **Groq Llama 3.3 70B** (free) | If Gemini quota hit |
| Video processing | **FFmpeg** (system binary) | Industry standard, free |
| Speaker/face detection | **MediaPipe** or **face_recognition** | Free, runs on CPU |
| Subtitle format | **ASS** (Advanced SubStation) burned via FFmpeg | Allows karaoke-style word highlight |
| Database | **SQLite** for now (single file) | Zero ops; migrate to Postgres later if needed |
| Job queue | **Simple SQLite-backed queue** initially → Celery+Redis later | Avoid premature complexity |
| Storage | **AWS S3** | User has $100 AWS credits |
| Compute | **AWS EC2** (t3.medium or spot) | User chose AWS over Hetzner for now |
| Scheduler | Deferred (manual posting for now) | Not in scope until clip quality is proven |
| Package manager | **uv** or **pip + venv** | User preference TBD |
| OS | Linux (Ubuntu 22.04 on EC2) | FFmpeg + Python tooling friendliest |

**Credentials user already has:** Groq API key, Gemini API key, AWS account ($100 credit).

**Cost target:** **$0 in new spend.** Everything must run on free tiers + AWS credit.

---

## 3. Architecture & File Structure

```
clipper-bot/
├── bot/
│   └── telegram_handler.py        # Accepts YT links, queues jobs, sends results
├── worker/
│   ├── download.py                 # yt-dlp wrapper, extracts audio + video + metadata
│   ├── transcribe.py               # Groq Whisper, returns word-level timestamps
│   ├── analyze.py                  # Gemini prompt → JSON list of clip ranges
│   ├── cut.py                      # FFmpeg cut + 16:9 export + 9:16 reframe
│   ├── reframe.py                  # MediaPipe speaker-aware vertical crop
│   └── subtitle.py                 # Word-level ASS generator + burn-in
├── db/
│   ├── models.py                   # SQLite schema (podcasts, clips)
│   └── queue.py                    # Simple job queue
├── storage/
│   └── s3.py                       # Upload clips, return signed URLs
├── prompts/
│   └── clip_selection.txt          # The Gemini prompt (iterate heavily here)
├── scheduler/                      # DEFERRED — empty for now
├── tests/
├── .env                            # GROQ_API_KEY, GEMINI_API_KEY, AWS_*, TG_BOT_TOKEN
├── requirements.txt
└── main.py                         # Entry point
```

### Data flow

```
User → Telegram link → Bot enqueues job
   ↓
Worker pulls job:
   1. yt-dlp downloads MP4 + extracts audio MP3
   2. Groq Whisper transcribes audio → word-level JSON
   3. Gemini analyzes transcript → JSON of 40-60 clip ranges
   4. For each clip:
       a. FFmpeg cuts 16:9 source segment
       b. MediaPipe detects active speaker per frame → 9:16 crop offsets
       c. ASS subtitle generated from word timestamps within clip range
       d. FFmpeg burns subs + outputs both 9:16 and 16:9 MP4s
       e. Upload to S3, store URLs + caption in DB
   5. Bot sends user a Telegram message with download links / files
```

---

## 4. What Is Built

**Nothing yet.** Project is in planning phase. This brain file is the first artifact.

---

## 5. What Is In Progress

Starting **Week 1 milestone**: bare-bones Telegram bot that accepts a YouTube link, downloads the video with yt-dlp, transcribes audio with Groq Whisper, and replies with the raw transcript.

Goal at end of Week 1: validate transcription quality on a real podcast before building anything downstream.

---

## 6. Roadmap / What's Next

Ordered, single-track. Don't skip ahead.

| # | Milestone | Scope | Success Criterion |
|---|---|---|---|
| 1 | **Telegram + Download + Transcribe** | Bot accepts link → yt-dlp → Groq Whisper → returns transcript file | Transcript looks accurate on a real podcast |
| 2 | **Gemini clip selection** | Feed transcript → get JSON of 40-60 clips with hooks + captions | User reviews 10 clips and agrees ≥6 are bangers |
| 3 | **FFmpeg basic cut + center-crop 9:16** | Cut clips, dumb center crop, no subs yet | Get watchable clips out the other end |
| 4 | **Subtitle generation (ASS) + burn-in** | Word-level highlighted captions, CapCut-style | Clips look "TikTok-ready" |
| 5 | **Speaker-aware 9:16 cropping** | MediaPipe face detection → smart pan crop | Clips with one active speaker are properly framed |
| 6 | **S3 upload + Telegram delivery** | Bot sends downloadable links/files for all clips | User can pull clips on phone, post manually to X |
| 7 | **Polish: caption quality, hook strength** | Iterate Gemini prompt based on what actually goes viral | Posted clips start getting traction on X |
| 8 | **DEFERRED — Auto-posting to X** | Only after milestone 7 produces consistently viral clips | User decides when to invest in X API or browser automation |

---

## 7. Known Bugs & Issues

None yet — nothing built.

**Anticipated friction points to watch for:**

- Groq's 25 MB audio upload limit → will need to chunk long podcasts (>~30 min) and stitch timestamps.
- Gemini free-tier rate limits (15 RPM) may bottleneck multi-podcast batches.
- yt-dlp breaks periodically when YouTube updates — pin to latest, retry with cookies if needed.
- MediaPipe speaker detection on multi-person podcasts (>2 speakers) is unreliable; may need fallback to center crop.

---

## 8. Decisions & Rationale

| Decision | Why | Alternative rejected |
|---|---|---|
| **Groq Whisper for transcription** | Free, fast, accurate, word-level timestamps | OpenAI Whisper API (paid), local Whisper (slow on CPU), Deepgram ($200 credit but limited) |
| **Gemini 2.0 Flash for clip selection** | Free, long context fits full transcripts | GPT-4 (paid), Claude (paid), Llama via Groq (smaller context) |
| **AWS over Hetzner** | User already has $100 credit; learn AWS along the way | Hetzner is better $/perf but starting AWS is fine while credits last |
| **SQLite over Postgres** | Zero ops, single-file, plenty for solo project | Postgres deferred until multi-user scale |
| **Manual X posting before automation** | Validate clip quality before paying for API or risking ToS violations | X API Basic ($200/mo) deferred; browser automation deferred |
| **Both 9:16 and 16:9 output** | 9:16 for Reels/Shorts/TikTok; 16:9 for X timeline + YouTube | 9:16-only would miss X engagement; 16:9-only would miss TikTok virality |
| **ASS subtitles burned in (not soft subs)** | Soft subs invisible in feed previews; burned subs always visible | Soft .srt/VTT — fail on social platforms |
| **Word-level subtitle highlighting (CapCut style)** | Proven format for retention on shorts | Sentence-at-a-time subtitles — feels dated |
| **Python over Node.js** | Best video/ML/bot ecosystem | Node has worse Python-equivalents for MediaPipe, Whisper, FFmpeg helpers |
| **Single worker process initially** | Avoid Celery/Redis complexity until proven needed | Celery deferred to milestone 6+ |

---

## 9. Conventions & Style

- **Python 3.11+**, type hints on all function signatures.
- **Black** formatter, **ruff** linter, defaults.
- Naming: `snake_case` for files/funcs/vars, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- Each module has a single responsibility (see §3 — `download.py` only downloads, `transcribe.py` only transcribes).
- Errors: raise specific exceptions, log with `logging` module (no `print` in production paths).
- **Secrets:** `.env` file via `python-dotenv`, never hardcoded, `.env` gitignored.
- **Commits:** conventional-commit style (`feat:`, `fix:`, `chore:`, `refactor:`).
- **Configurable values** (clip count, durations, paths) live in a single `config.py` — no magic numbers scattered across files.
- **All paths** absolute or rooted at project root via `pathlib.Path`.

---

## 10. Anti-Patterns / "Don't Do This"

- ❌ **Don't suggest paid services.** No paid APIs, no SaaS subscriptions, no X API tier upgrades. Free tier or AWS credit only, until user explicitly says otherwise.
- ❌ **Don't suggest automating X posting yet.** Deferred until clip quality is proven via manual posting.
- ❌ **Don't suggest moving off AWS yet.** User chose AWS while credits last; revisit only when credits near zero.
- ❌ **Don't recommend Twitter/X API Free tier for media posting** — it's broken/restrictive and known not to work for this use case.
- ❌ **Don't suggest Selenium/Playwright browser automation for X** unless the user brings it up — ToS risk.
- ❌ **Don't add Celery/Redis/Postgres** until SQLite + single worker is proven insufficient.
- ❌ **Don't over-engineer.** Single worker, single SQLite file, no microservices, no Docker Swarm. Solo project.
- ❌ **Don't suggest Whisper running locally** unless Groq fails — slower and pointless when Groq is free.
- ❌ **Don't refactor working code prematurely.** Get end-to-end working first, then improve quality.
- ❌ **No TypeScript/Node.js rewrites.** Python stays.

---

## 11. My Working Style & Preferences

*(Defaults inferred from conversation — user can correct.)*

- **Code-first, explanation-second.** User wants concrete code, prompts, and architecture more than theory.
- **Pragmatic over perfect.** "Get it working" > "build it right." Iterate.
- **Wants honest pushback** on flawed plans (e.g., I flagged the X API cost issue — user appreciated the heads-up).
- **Ask before assuming** on big architectural pivots; just-do-it on small implementation choices.
- **Skill level:** comfortable with Python, building MVPs, AWS (learning); unsure of comfort with FFmpeg, MediaPipe, ASS subtitle format — explain these as we go.
- **Solo founder mindset** — wants a real product that earns money, not a polished portfolio piece.
- **Prefers full file when changing it**, diffs are fine for small edits.
- **Likes structured responses** with headers and tables for planning docs; keep prose tight.

---

## 12. Open Questions & Pending Decisions

| Question | Options | Leaning |
|---|---|---|
| Package manager: `pip+venv` vs `uv` vs `poetry`? | Any | Probably `uv` (fast, modern) |
| EC2 instance type? | t3.medium / t3.large / spot | Start t3.medium, evaluate |
| Where does worker run during dev? | Local machine vs EC2 from day 1 | Local for milestones 1–4, EC2 from milestone 5+ |
| Telegram bot delivery: send video files or S3 links? | Files (≤50MB) vs links | Probably links (Telegram caps file size; clips × 80 = lots) |
| How to handle multi-speaker podcasts in 9:16 crop? | Pick loudest, split-screen, fallback to center | TBD — test on real footage |
| Subtitle font choice? | Inter Black, Montserrat Black, Bebas Neue | TBD — A/B test on first batch |
| How many clips to ask Gemini for vs filter to? | Ask 60, keep top 40-50 by score | Confirmed |
| Caption style: question hook, statement, or quote? | All three, test what hits | TBD |

---

## 13. External Context

- **Groq API:** https://console.groq.com — free tier, key in `.env` as `GROQ_API_KEY`
- **Gemini API:** https://aistudio.google.com — free tier, key in `.env` as `GEMINI_API_KEY`
- **AWS:** $100 credit account, IAM keys in `.env` as `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, region likely `us-east-1` or closest
- **Telegram BotFather:** for bot token, key in `.env` as `TG_BOT_TOKEN`
- **Reference projects to study (open source):**
  - **ClipsAI** — https://github.com/ClipsAI/clipsai (Python, similar concept, Apache-2.0)
  - **AutoFlip** (Google) — speaker-aware reframing
  - **autoshorts** style projects on GitHub for inspiration on subtitle styling
- **Reference style accounts on X for clip benchmarks** — TBD, user to share favorites
- **No design files, no existing repo yet** — building from scratch.

---

## 14. Glossary / Domain Terms

| Term | Meaning |
|---|---|
| **Viral clip** | 30–120s self-contained moment from a podcast that hooks viewers in <3s and ends on a punchline/insight |
| **9:16** | Vertical aspect ratio for Reels, Shorts, TikTok (1080×1920) |
| **16:9** | Horizontal aspect ratio for X timeline, YouTube (1920×1080) |
| **Hook** | First 1–3 seconds of a clip; determines whether viewer keeps watching |
| **ASS** | Advanced SubStation Alpha — subtitle format with styling, used for karaoke-style highlighted captions |
| **Burn-in subtitles** | Subtitles rendered permanently into video pixels (vs. soft subs in a separate track) |
| **Active speaker detection** | Per-frame ID of which face is currently talking (mouth movement); used to pan the 9:16 crop window |
| **Center crop** | Naive 9:16 reframing — just take the middle vertical strip of the 16:9 source |
| **Speaker-aware crop** | Smart 9:16 reframing using face detection to keep the active speaker in frame |
| **Virality score** | Gemini-assigned 0–10 score per clip, used to filter top N |
| **Word-level timestamps** | Start/end time for every individual word, needed for highlighted-word subtitle style |
| **CapCut style** | De facto subtitle look on TikTok: large bold sans-serif, white with black stroke, current word highlighted yellow, lower-third position |
| **Credit line** | "🎙️ Channel Name" appended to caption to attribute source podcast |

---

## 🔁 Maintenance Ritual

After every dev session, update:

1. **§4 What Is Built** — append what now works
2. **§5 What Is In Progress** — replace with current task
3. **§7 Known Bugs** — add anything you hit
4. **§12 Open Questions** — close resolved ones, add new ones
5. **Last Updated** date at the top

This file is the project's persistent memory. Treat it as production code — keep it accurate, keep it terse, keep it current.

---

*End of brain. Total length kept under 3000 words for context-window friendliness.*
