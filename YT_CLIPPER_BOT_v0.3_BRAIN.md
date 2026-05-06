# YT Clipper Bot — Project Brain

**Created:** 2026-05-06
**Last Updated:** 2026-05-06 (M1 SHIPPED, M2 starting)
**Version:** v0.3

---

## 🧠 Resume Instructions (READ FIRST)

You are picking up a project mid-flight. Before responding to anything:

1. Read this entire file end-to-end. Every section.
2. Confirm understanding back to the user in 2–3 lines (what's built, what's next).
3. Ask what they want to tackle.

**Hard rules to internalize before touching code:**
- No paid services suggestions unless user raises it. Free/credit-tier only.
- Do not auto-deploy to AWS until M3 (clip cutting) is also working — user agreed AWS is for the *complete clipper*, not transcript bot.
- Do not suggest Twitter/X API automation. User posts manually until clip quality is proven.
- Do not use stable yt-dlp from PyPI — it's broken for current YouTube. Use `git+https://github.com/yt-dlp/yt-dlp.git` (master) + Deno. See §13.

---

## 1. Project Snapshot

**A Telegram bot that takes YouTube podcast links and returns 40–50 viral short clips per podcast** in 9:16 (Reels/Shorts/TikTok) and 16:9 (X/YouTube) formats, each with burned-in subtitles and a tweet-ready caption + channel credit.

**User goal:** post clips manually on X.com to grow followers, get monetized, earn from posting. Auto-posting is **deferred** until clip quality is validated.

**Phase:** Milestone 1 (transcription) is **shipped and verified**. Currently starting Milestone 2 (Gemini → viral clip ranges).

---

## 2. Tech Stack & Environment

| Layer | Choice | Notes |
|---|---|---|
| OS | macOS (M-series MacBook Air, 8GB RAM, ~90GB disk) | All dev local for now |
| Python | **3.12.13** (via `brew install python@3.12`) | System Python 3.9.6 is too old, do not use |
| Bot framework | **python-telegram-bot 22.7+** | Async, long-polling (no webhooks) |
| Video downloader | **yt-dlp master from git** + **Deno JS runtime** (`brew install deno`) | Stable PyPI versions are broken for YouTube. Master + Deno required. |
| Transcription | **Deepgram Nova-3** (free $200 credit, no card) | Single-call, multi-language mode handles Hindi/English code-switching. ~9 sec for 15-min audio. |
| Clip selection LLM | **Gemini 2.5 Flash-Lite** (free tier: 30 RPM, 1500 RPD, 1M TPM) | Long context handles full 3-hr transcripts in one call. ⚠️ Gemini 2.0 Flash deprecated March 3, 2026. |
| Backup LLM | Groq Llama 3.3 70B (free) | Fallback if Gemini quota hits |
| Video processing | **FFmpeg 8.1.1** (system binary) | M3+ |
| Speaker detection | **MediaPipe** | M5 |
| Subtitle format | **ASS** (burned-in via FFmpeg) | M4, CapCut-style word highlighting |
| Database | **SQLite** (single file) | Zero ops; deferred until needed |
| Storage | **Local disk now → AWS S3 from M6+** | Don't burn $100 credit on dev-phase storage |
| Compute | **Local Mac (dev) → AWS EC2 only at M7+ if 24/7 is wanted** | M-series Mac > t3.medium for video work |
| Package manager | `pip + venv` | Standard, not `uv` (didn't migrate) |

**Project path on user's machine:** `/Users/mohitchaprana/Downloads/YT Clipper/` (note the space, must be quoted in shell)

**Cost budget:** **$0 in new spend** until clips are proven viral. AWS $100 credit untouched.

---

## 3. Architecture & File Structure

```
YT Clipper/                              ← user's project root (note space in name)
├── main.py                               # entry point: `python main.py`
├── config.py                             # env loading + settings
├── .env                                  # gitignored secrets
├── .env.example                          # template
├── .gitignore
├── requirements.txt
├── README.md                             # setup instructions
├── .venv/                                # Python 3.12 virtual env
├── workdir/                              # runtime files (gitignored)
│   └── <video_id>/                       # per-podcast outputs
│       ├── transcript.txt                # plain text
│       ├── transcript.json               # text + word-level + segment timestamps
│       └── clips.json                    # M2 output: viral clip ranges + captions
├── bot/
│   ├── __init__.py
│   └── telegram_handler.py               # /start, /help, /status, /clean, message handler
└── worker/
    ├── __init__.py
    ├── download.py                       # yt-dlp wrapper, MP3 caching, cookies/Deno support
    ├── transcribe.py                     # Deepgram Nova-3
    └── analyze.py                        # M2 (NOT YET) — Gemini → clips
```

### Data flow (current + planned)

```
Telegram link
    ↓
download.py:        yt-dlp → MP3 (16kHz mono 64kbps) → cache by video_id
    ↓
transcribe.py:      Deepgram Nova-3 → transcript.json (text, words, segments)
    ↓
[M2] analyze.py:    Gemini → clips.json (40-60 ranges with hooks + captions)
    ↓
[M3] cut.py:        FFmpeg → clip MP4s (16:9, no subs yet)
    ↓
[M4] subtitle.py:   ASS gen + burn-in → captioned MP4s
    ↓
[M5] reframe.py:    MediaPipe + FFmpeg → 9:16 reframed MP4s
    ↓
[M6] s3.py:         upload → signed URLs in DB
    ↓
Bot replies via Telegram with: clips.json + (eventually) clip files / S3 URLs
```

---

## 4. What Is Built

### ✅ Milestone 1 — SHIPPED (2026-05-06, verified on a 15-min Robert Greene clip in 41 seconds end-to-end)

- ✅ Project scaffold + venv + dependencies installed
- ✅ Telegram bot accepts YouTube URLs (validates with regex)
- ✅ `/start`, `/help`, `/status` (disk usage), `/clean` (wipe MP3 cache) commands
- ✅ `download.py`: yt-dlp master with Deno runtime, multi-player-client extraction, MP3 caching, cookie support (currently disabled — see §7)
- ✅ `transcribe.py`: Deepgram Nova-3 single-call transcription with word-level timestamps, multi-language detection
- ✅ Auto-cleanup: MP3 deleted on success, kept on failure for retry
- ✅ Per-podcast output saved to `workdir/<video_id>/transcript.{json,txt}`
- ✅ Bot replies in Telegram with both files
- ✅ Disk impact after success: <1MB per podcast (just transcripts)

### ❌ Not yet built

- M2: Gemini clip analysis ← **starting now**
- M3: FFmpeg clip cutting
- M4: ASS subtitle generation + burn-in
- M5: Speaker-aware 9:16 reframing (MediaPipe)
- M6: S3 upload + signed URLs
- M7: Auto-posting to X (deferred indefinitely)

---

## 5. What Is In Progress

**Starting Milestone 2:** `worker/analyze.py` — feed `transcript.json` to Gemini 2.5 Flash-Lite, get back 40–60 viral clip ranges with hooks, tweet captions, virality scores, and reasoning.

The viral-clip selection prompt is the most important piece of the entire system. **Most of the value lives in this prompt.** Will iterate aggressively based on what Gemini picks vs what user picks.

User has confirmed they have a Gemini API key, just need to add it to `.env`.

---

## 6. Roadmap / What's Next

| # | Milestone | Scope | Success criterion |
|---|---|---|---|
| **2** | **Gemini clip selection** | `worker/analyze.py` + bot integration; output `clips.json` | User reviews top 10 clips and agrees ≥6 are bangers |
| 3 | FFmpeg cutting (16:9 + naive 9:16 center-crop), no subs | `worker/cut.py` | Watchable clips out the other end |
| 4 | ASS subtitles + FFmpeg burn-in (CapCut style) | `worker/subtitle.py` | Clips look "TikTok-ready" |
| 5 | Speaker-aware 9:16 cropping (MediaPipe) | `worker/reframe.py` | Single-speaker clips properly framed |
| 6 | S3 upload + Telegram delivery as URLs | `storage/s3.py` | User can pull clips on phone for manual posting |
| 7 | Polish caption quality, hook strength | Iterate prompt | Clips start getting traction on X |
| 8+ | Auto-posting to X (deferred) | Only after #7 produces consistently viral clips | TBD |

**AWS deploy comes after M5 or M6 — when there's a real clipper to deploy, not a transcript bot.**

---

## 7. Known Bugs & Issues

| # | Issue | Status | Notes |
|---|---|---|---|
| 1 | Stable yt-dlp on PyPI (any version up to `2026.3.17`) fails on YouTube with "Requested format is not available" | **WORKAROUND APPLIED** | Must install from `git+https://github.com/yt-dlp/yt-dlp.git` (master) AND have Deno installed (`brew install deno`). yt-dlp now needs a JS runtime to solve YouTube's signature challenges. |
| 2 | Cookies passed via `COOKIES_FROM_BROWSER` make yt-dlp's `2026.3.17` stopgap WORSE (release notes: "Some formats may still be unavailable, especially if cookies are passed to yt-dlp") | **WORKAROUND APPLIED** | Removed `COOKIES_FROM_BROWSER` from `.env`. Re-test if cookies are needed for age-restricted videos later. |
| 3 | macOS Terminal session restore loses venv activation | **DOCUMENTED** | After "Restored session", always run `cd "/Users/mohitchaprana/Downloads/YT Clipper" && source .venv/bin/activate` before any `python` command. |
| 4 | zsh treats `#` as command (not comment) in interactive mode | **DOCUMENTED** | Don't paste command blocks with `# comments` to user — they break. Use prose to explain instead. |

**Resolved bugs (kept for memory):**
- ❌ Groq SDK API change (objects → dicts) → swapped to Deepgram entirely
- ❌ Groq rate limit (7200 sec audio/hour) → Deepgram has no limits at our scale
- ❌ Wrong Telegram token (stray `y` prefix from BotFather copy-paste) → user revoked + regenerated
- ❌ Python 3.9.6 (system) → installed 3.12 via brew
- ❌ Hit YouTube bot detection ("Sign in to confirm you're not a bot") → solved by Deno + yt-dlp master, cookies turned out unnecessary

---

## 8. Decisions & Rationale

| Decision | Why | Alternative rejected |
|---|---|---|
| **Deepgram over Groq Whisper** | Groq's 7200 sec/hr rate limit makes 3-hour podcasts take 4+ hours wall-time. Deepgram: 9 sec for 15min, no chunking, no rate limits at our scale. $200 free credit ≈ 775 hours = 2+ months of usage at user pace. | Groq Whisper (rate limited), AssemblyAI (only 5 hrs free), local Whisper (slow on CPU) |
| **yt-dlp master + Deno over stable** | Stable yt-dlp is broken for current YouTube. Master + Deno is the working combo as of May 2026. | Stable yt-dlp (doesn't work), youtube-dl (worse) |
| **Gemini 2.5 Flash-Lite for clip selection** | 30 RPM, 1500 RPD, 1M TPM free tier. Long context fits 3-hr transcripts in one call. | Gemini 2.0 Flash (deprecated March 3, 2026), Gemini 2.5 Pro (only 50 RPD), GPT-4 (paid), Claude (paid) |
| **Local Mac for M1–M5, S3 from M6** | M-series Mac is faster than t3.medium for video work. EC2 burns ~$10–30/mo. $100 credit lasts longer if saved for M6/M7. Iteration on Mac is 10x faster than SSH + redeploy. | EC2 from day 1 (premature, expensive), Hetzner (user prefers AWS while credit lasts) |
| **Manual posting to X before automation** | Validate clip quality before paying for X API ($200/mo) or risking ToS via browser automation. | X API Basic now (premature spend), Selenium automation (ToS risk) |
| **9:16 + 16:9 both** | 9:16 for Reels/Shorts/TikTok feed previews; 16:9 for X timeline + YouTube. | Either alone misses traction on the other side |
| **ASS burned-in subtitles, CapCut-style word highlighting** | Soft subs are invisible in feed previews. Burned-in is the standard for viral shorts. Word-level highlight (yellow current word, white rest) is the proven retention pattern. | Soft .srt/VTT (invisible in feed), sentence-at-a-time subs (looks dated) |
| **Auto-cleanup MP3 on success, keep on failure** | Zero disk footprint after success. On failure, retries skip the redownload. | Always-keep (wastes 80MB/podcast on user's tight 90GB Mac) |
| **SQLite over Postgres, single-process worker over Celery** | Solo project; premature complexity. | Postgres + Redis (deferred until proven need) |
| **Python 3.12 over 3.9** | python-telegram-bot v22 + modern type hints. 3.9.6 is system Python and old. | System Python (too old) |

---

## 9. Conventions & Style

- **Python 3.12+**, type hints on function signatures.
- **Black** formatter, **ruff** linter, defaults.
- `snake_case` files/funcs/vars; `PascalCase` classes; `UPPER_SNAKE` constants.
- One responsibility per module (e.g. `download.py` only downloads).
- `logging` (no `print` in prod paths).
- All paths via `pathlib.Path`, rooted at project root.
- Configurable values centralized in `config.py` — no magic numbers in worker code.
- Secrets via `python-dotenv`, `.env` gitignored.
- Conventional commits: `feat:`, `fix:`, `chore:`, `refactor:`.

---

## 10. Anti-Patterns / "Don't Do This"

- ❌ **No paid services** unless user explicitly raises it.
- ❌ **No automating X posting yet.** Deferred until clip quality is proven.
- ❌ **No EC2 for transcript-only bot.** AWS comes when there's a *real clipper* to deploy (M5/M6+).
- ❌ **No stable yt-dlp.** Always use `git+https://github.com/yt-dlp/yt-dlp.git`.
- ❌ **No Whisper local.** Slow on CPU, defeats Deepgram speed advantage.
- ❌ **No Celery/Redis/Postgres** until single-worker SQLite is proven insufficient.
- ❌ **No `# comments` in command blocks pasted to user** — zsh treats `#` as a command in interactive mode.
- ❌ **No mention of project files via spaces in shell** without quoting — user's path has a space.
- ❌ **No premature refactoring.** Get end-to-end working first, polish later.
- ❌ **No TypeScript/Node rewrites.** Python stays.
- ❌ **Don't suggest cookies for yt-dlp** unless user hits an age-restricted video. Cookies caused issues with the stopgap version.

---

## 11. My Working Style & Preferences

(Inferred from a long debugging session — user can correct.)

- **Code-first, explanation-second.** Wants concrete code, not theory.
- **Pragmatic over perfect.** "Get it working" beats "build it right."
- **Appreciates honest pushback.** Asked for AWS deploy of M1; I pushed back on "it's only a transcript bot, deploy when it's a real clipper" — user agreed.
- **Skill level:** comfortable with Python concepts, building MVPs, AWS (learning); learning curve on FFmpeg, MediaPipe, ASS subtitles — explain those clearly when they come up.
- **Mac terminal experience:** intermediate. Sometimes loses venv after session restore — remind to re-activate.
- **Tendency to want shortcuts** ("ditch subtitles", "deploy now") — push back when shortcuts hurt the goal, agree when they don't.
- **Solo founder mindset.** Wants real product earning money on X.
- **Prefers full file rewrites over diffs** for clarity.
- **Likes structured responses** with tables for plans, tight prose otherwise.
- **Frustration tolerance:** moderate. After several failures, suggest a clean working path forward rather than more debugging.

---

## 12. Open Questions & Pending Decisions

| Question | Options | Leaning |
|---|---|---|
| Subtitle font for M4 | Inter Black, Montserrat Black, Bebas Neue | TBD — A/B test on first batch |
| Caption styles to support in MVP | Just `highlighted` + `minimalist`, or all 5 (Vugola has highlighted/scale/minimalist/box/none) | Confirmed: start with `highlighted` + `minimalist` |
| Multi-speaker 9:16 crop | Pick loudest, split-screen, fallback to center | TBD — test on real footage |
| Caption hook style | Question hook vs statement vs quote | A/B test on first 20 posted clips |
| When to switch transcripts to chunking | When podcasts >5 hours? | Not needed yet — Deepgram handles full files |
| Reference X accounts for benchmark style | TBD | User to share favorites |

---

## 13. External Context

### API keys (in `.env`, all gitignored)

- `TG_BOT_TOKEN` — Telegram bot token from @BotFather. **Has been revoked once already** after accidental exposure. Treat as sensitive.
- `DEEPGRAM_API_KEY` — Deepgram Nova-3, $200 credit, no card. https://console.deepgram.com
- `GEMINI_API_KEY` — Gemini 2.5 Flash-Lite, free tier. https://aistudio.google.com (user has it; needs to be added to `.env` for M2)
- `GROQ_API_KEY` — legacy, optional, no longer used (kept in case of fallback)
- `COOKIES_FROM_BROWSER` — currently unset. If we re-enable: `safari` works on macOS without keychain prompts; `chrome` requires keychain access.

### AWS

- $100 credit account active. **Not yet touched.** First use planned for M6 (S3 storage).
- Region: probably `us-east-1` or `ap-south-1` (Mumbai) for India proximity. TBD.

### Reference projects

- **ClipsAI** — https://github.com/ClipsAI/clipsai (Python, similar concept, Apache-2.0). Worth reading their code before reinventing.
- **Vugola** — paid SaaS competitor at $9/$29/$99 per month. Not usable for us (paid only) but their feature spec is a good reference: aspect ratios `9:16`/`1:1`/`16:9`, caption styles `highlighted`/`scale`/`minimalist`/`box`/`none`, virality scoring.
- **AutoFlip** (Google) — speaker-aware reframing, reference for M5.
- **CapCut** — commercial reference for subtitle aesthetic in M4.

### Critical install commands (replicate in any new env)

```bash
brew install ffmpeg python@3.12 deno
# In project dir:
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# yt-dlp specifically — must be master, not stable:
pip install --upgrade --force-reinstall --no-cache-dir \
    "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git"
```

---

## 14. Glossary / Domain Terms

| Term | Meaning |
|---|---|
| Viral clip | 30–120s self-contained moment that hooks viewers in <3s and ends on a punchline/insight |
| 9:16 | Vertical aspect for Reels/Shorts/TikTok (1080×1920) |
| 16:9 | Horizontal aspect for X timeline / YouTube (1920×1080) |
| Hook | First 1–3s of a clip; determines retention |
| ASS | Advanced SubStation Alpha subtitle format with styling, used for word-highlighted captions |
| Burned-in subtitles | Subtitles rendered into video pixels (vs separate soft subs) |
| Active speaker detection | Per-frame ID of which face is talking, used to pan 9:16 crop |
| Center crop | Naive 9:16 reframing — middle vertical strip of 16:9 |
| Speaker-aware crop | Smart 9:16 reframing using face detection to keep speaker in frame |
| Virality score | Gemini-assigned 0–10 score per clip |
| Word-level timestamps | Start/end time per word, needed for highlighted-word subtitle style |
| CapCut style | TikTok subtitle look: large sans-serif, white + black stroke, current word highlighted yellow, lower-third position |
| Credit line | "🎙️ Channel Name" appended to caption |
| Deno | JS runtime that yt-dlp now requires to solve YouTube's signature challenges |
| Stopgap release | yt-dlp 2026.3.17 — partial YouTube fix; cookies make it worse |

---

## 🔁 Maintenance Ritual

After every dev session, update:

1. **§4 What Is Built** — append what now works
2. **§5 What Is In Progress** — replace with current task
3. **§7 Known Bugs** — add new issues, mark resolved
4. **§12 Open Questions** — close resolved, add new
5. **Last Updated** date at top, bump version

This file is the project's persistent memory. Treat as production code: accurate, terse, current.

---

*End of brain v0.3.*
