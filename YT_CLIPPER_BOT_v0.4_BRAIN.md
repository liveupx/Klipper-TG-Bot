# YT Clipper Bot — Project Brain

**Created:** 2026-05-06
**Last Updated:** 2026-05-06 (M3 shipped end-to-end; awaiting clip quality verification)
**Version:** v0.4

---

## 🧠 Resume Instructions (READ FIRST)

You are picking up an in-flight project. Before responding to anything:

1. Read this file end-to-end.
2. Confirm understanding to the user in 2–3 lines (what works, what's next).
3. Ask what they want to tackle.

**Hard rules — internalize before touching code:**
- No paid services unless user explicitly raises it. Free / credit-tier only.
- Do not auto-deploy to AWS until M4–M6 land. AWS is for *complete clipper*, not transcript/clip stub.
- Do not suggest Twitter/X API automation. User posts manually until clips are proven viral.
- Do not use stable yt-dlp from PyPI — broken for current YouTube. Always master + Deno. See §13.
- Do not use FFmpeg `-c copy` for cuts — A/V desync risk. We re-encode (slower, reliable).

---

## 1. Project Snapshot

**A Telegram bot that takes YouTube podcast links and returns viral short MP4 clips** (40+ per podcast at scale; 8–12 per short video) in 9:16 (Reels/Shorts/TikTok) and 16:9 (X/YouTube) formats, with auto-generated tweet captions and channel credits.

**User goal:** post clips manually on X.com to grow followers, get monetized, earn from posting. Auto-posting is **deferred** until clip quality is validated.

**Current phase:** M1 (transcription) ✅ + M2 (clip selection) ✅ + M3 (cutting) ✅. **End-to-end pipeline produces actual MP4 files.** Awaiting user feedback on clip quality before deciding M4 vs M5 next. AWS deploy comes after M4–M6.

---

## 2. Tech Stack & Environment

| Layer | Choice | Notes |
|---|---|---|
| OS | macOS (M-series MacBook Air, 8GB RAM, ~90GB disk) | All dev local |
| Python | **3.12.13** (`brew install python@3.12`) | System 3.9.6 unusable |
| Bot framework | **python-telegram-bot 22.7+** | Async, long-polling |
| Video downloader | **yt-dlp master from git** + **Deno JS runtime** | Stable PyPI broken; master + Deno required |
| Transcription | **Deepgram Nova-3** (free $200 credit) | Single-call, no chunking, multi-language; ~9s for 15-min audio |
| Clip selection LLM | **Gemini 2.5 Flash-Lite** (free tier: 30 RPM, 1500 RPD) | Long context fits 3-hr transcripts in one call |
| Video cutting | **FFmpeg 8.1.1** (system binary) | `libx264 preset fast crf 20`, re-encoded for clean A/V |
| Backup LLM | Groq Llama 3.3 70B (free) | Fallback if Gemini quota hits |
| Speaker detection | MediaPipe | M5 |
| Subtitle format | ASS (burned-in via FFmpeg) | M4 |
| Database | SQLite | Deferred until needed |
| Storage | Local disk now → AWS S3 from M6+ | $100 AWS credit untouched |
| Compute | Local Mac (dev) → AWS EC2 from M7+ if 24/7 wanted | M-series Mac > t3.medium for video |

**User project path:** `/Users/mohitchaprana/Downloads/YT Clipper/` (note space, must be quoted)

**Cost budget:** **$0 in new spend** until clips proven viral.

---

## 3. Architecture & File Structure

```
YT Clipper/
├── main.py                               # entry point
├── config.py                             # env loading + validation (TG, Deepgram, Gemini)
├── .env                                  # gitignored secrets
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── .venv/                                # Python 3.12 venv
├── workdir/                              # runtime files (gitignored)
│   ├── <video_id>.mp3                    # cached audio (auto-deleted on success)
│   ├── <video_id>.mp4                    # cached source video (auto-deleted on success)
│   └── <video_id>/                       # per-podcast outputs
│       ├── transcript.txt
│       ├── transcript.json
│       ├── clips.json
│       └── clips/
│           ├── <id>_clip01_16x9.mp4      # 1080p, X-ready
│           ├── <id>_clip01_9x16.mp4      # 1080×1920, Reels/Shorts-ready
│           └── ...
├── bot/
│   ├── __init__.py
│   └── telegram_handler.py               # /start, /help, /status, /clean, /cliponly + handler
└── worker/
    ├── __init__.py
    ├── download.py                       # yt-dlp audio download + caching
    ├── download_video.py                 # yt-dlp video download (720p capped)
    ├── transcribe.py                     # Deepgram Nova-3
    ├── analyze.py                        # Gemini → clips.json (the most important file)
    └── cut.py                            # FFmpeg cuts clips, produces 16:9 + naive 9:16
```

### Data flow (current state — all the way to MP4 delivery)

```
Telegram link
    ↓
download.py:        yt-dlp → MP3 (16kHz mono 64kbps) → cache
    ↓
transcribe.py:      Deepgram Nova-3 → transcript.json + .txt
    ↓
analyze.py:         Gemini 2.5 Flash-Lite → clips.json (8–60 ranked viral ranges)
    ↓
download_video.py:  yt-dlp → 720p MP4 → cache
    ↓
cut.py:             FFmpeg per clip:
                      • 16:9 cut (re-encoded libx264, AAC audio)
                      • 9:16 naive center-crop (smart crop is M5)
    ↓
telegram_handler:   sends to user:
                      • transcript.txt
                      • clips.json
                      • per clip: header msg + 16:9 MP4 + 9:16 MP4
    ↓
Auto-cleanup:       MP3 + MP4 + clips/ folder deleted on success
```

**Verified runtime (15-min source video, 12 clips produced):**
- Download audio: ~25s
- Transcribe: ~9s
- Gemini analysis: ~25s
- Download video: ~30s
- Cut clips: ~25s/clip × 12 = ~5 min
- **Total end-to-end: ~7 min** for a short-form source

---

## 4. What Is Built

### ✅ M1 — Transcription pipeline (shipped 2026-05-06)
- Project scaffold + venv + dependencies
- Telegram bot accepts YT URLs (regex validation)
- `/start`, `/help`, `/status`, `/clean`, `/cliponly` commands
- yt-dlp master + Deno runtime; bypasses YouTube bot detection
- MP3 caching by video_id (skip re-download on retry)
- Deepgram Nova-3 transcription with word-level timestamps + multi-language
- Auto-cleanup MP3 on success, kept on failure for retry

### ✅ M2 — Gemini clip selection (shipped 2026-05-06)
- `worker/analyze.py` with iteratively-refined viral-clip prompt
- Gemini 2.5 Flash-Lite (free tier)
- Prompt asks for 60 clips, sanitizes + filters, sorts by virality_score
- Output: `clips.json` with `{start, end, duration, hook, caption, virality_score, reason, topic}`
- Per-clip caption generated by Gemini; channel credit ("🎙 Channel Name") appended downstream
- Top-5 preview sent to Telegram inline as Markdown summary
- **Verified:** 8–12 clips per 15-min source, scores 7.0–9.0 (median ~7.5–8.5)

### ✅ M3 — FFmpeg clip cutting (shipped 2026-05-06)
- `worker/download_video.py` — 720p MP4 download with yt-dlp + Deno
- `worker/cut.py` — per-clip FFmpeg pipeline:
  - 16:9 cut: `libx264 preset fast crf 20`, AAC 128k, faststart, yuv420p
  - 9:16 crop: `scale=-2:1920,crop=1080:1920` from the 16:9 output (re-encoded)
- Caps deliveries at top 20 clips per source (Telegram upload limits)
- Sends each clip with: header msg (score, hook, timestamps, caption preview) → 16:9 MP4 → 9:16 MP4 (each captioned with full text + 🎙 credit)
- Auto-cleanup: MP3 + MP4 + per-clip folder deleted on success
- **Verified:** 12/12 clips cut + uploaded for a 15-min source in ~7 min total

### ❌ Not yet built
- M4: Burned-in CapCut-style subtitles (ASS format, word-level highlighting)
- M5: Speaker-aware 9:16 cropping (MediaPipe, replaces naive center-crop)
- M6: S3 upload + signed URLs (Telegram becomes link-only, not file-only)
- M7: Auto-posting to X (deferred indefinitely — manual posting first)

---

## 5. What Is In Progress

**Awaiting user verification on M3 clip quality.** Specifically:

1. Do all 12 clips actually arrive in Telegram?
2. Does the highest-scored clip play with synced A/V?
3. **Critical:** does the 9:16 naive center-crop keep the speaker on-screen, or are they cropped off?
4. Does posting one manually to X look reasonable?

**Next step depends on answer to #3:**
- If 9:16 frames the speaker correctly → **build M4 (burned-in subtitles)** — the biggest visual upgrade
- If 9:16 cuts speaker off → **build M5 first (speaker-aware cropping)** before M4

---

## 6. Roadmap / What's Next

| # | Milestone | Scope | Success criterion | Status |
|---|---|---|---|---|
| 1 | Transcription | Deepgram + caching | Accurate transcript per podcast | ✅ |
| 2 | Clip selection | Gemini → clips.json | Top 5 are bangers per user | ✅ |
| 3 | FFmpeg cutting | 16:9 + naive 9:16 MP4s | Watchable clips delivered to Telegram | ✅ |
| **4** | **Burned-in subtitles** | ASS file gen + FFmpeg burn-in, CapCut style | Clips look "TikTok-ready" | **Next (likely)** |
| **5** | **Speaker-aware 9:16** | MediaPipe face-track + dynamic crop | Single-speaker clips properly framed | **Next (if 9:16 broken)** |
| 6 | S3 upload + delivery | Replace MP4 file send with signed URLs | User pulls clips from S3 link | After M4–M5 |
| 7 | Caption / hook polish | Iterate Gemini prompt based on what hits on X | Posted clips get traction | Ongoing |
| 8 | AWS deploy | EC2 spot + S3 for full pipeline | Bot online 24/7, S3-backed | After M6 |
| 9+ | Auto-posting to X | X API or aggregator (Ayrshare-style) | Scheduled posts every 30 min | Deferred |

---

## 7. Known Bugs & Issues

| # | Issue | Status | Notes |
|---|---|---|---|
| 1 | Stable yt-dlp from PyPI breaks on YouTube | **WORKAROUND APPLIED** | Use `git+https://github.com/yt-dlp/yt-dlp.git` master + `brew install deno` |
| 2 | Cookies passed to yt-dlp 2026.3.17 stopgap make it WORSE | **WORKAROUND APPLIED** | `COOKIES_FROM_BROWSER` left unset; only re-enable for age-restricted videos |
| 3 | macOS Terminal session restore loses venv | **DOCUMENTED** | After "Restored session" remind user: `cd <project> && source .venv/bin/activate` |
| 4 | zsh treats `#` as command in interactive mode | **DOCUMENTED** | Don't paste `# comments` in command blocks to user |
| 5 | FFmpeg cut takes ~25s/clip (re-encode for both 16:9 + 9:16) | **ACCEPTED** | Trade-off vs `-c copy` (which causes A/V desync). Optimize only if scaling demands it. |
| 6 | Telegram caps document upload at ~50MB | **MITIGATED** | Caps clip output to top 20 per podcast; clips at 720p re-encode are ~5–15 MB each |
| 7 | 9:16 is naive center-crop — speaker may be cut off | **KNOWN, M5 fixes** | Will revisit if user confirms it's an issue |

**Resolved (kept for memory):**
- ❌ Groq SDK API change (objects → dicts) → switched to Deepgram entirely
- ❌ Groq rate limit (7200 sec/hr) → Deepgram has none at our scale
- ❌ Wrong Telegram token (stray `y` from BotFather copy-paste) → revoked + regenerated
- ❌ Python 3.9.6 too old → installed 3.12 via brew
- ❌ YouTube bot detection ("Sign in to confirm…") → solved by Deno + master yt-dlp; cookies unnecessary

---

## 8. Decisions & Rationale

| Decision | Why | Rejected alternative |
|---|---|---|
| **Deepgram over Groq Whisper** | Groq's 7200 sec/hr rate limit makes 3-hr podcasts take 4+ hr wall-time. Deepgram: 9s for 15min. $200 credit ≈ 775 hours = 2+ months of usage. | Groq (rate limited), AssemblyAI (only 5 hrs free), local Whisper (slow CPU) |
| **yt-dlp master + Deno over stable** | Stable broken for current YouTube; master + Deno works. | Stable yt-dlp, youtube-dl |
| **Gemini 2.5 Flash-Lite for clip selection** | 30 RPM, 1500 RPD, 1M TPM free. Fits 3-hr transcripts in one call. | Gemini 2.0 Flash (deprecated), 2.5 Pro (only 50 RPD), GPT-4 (paid), Claude (paid) |
| **FFmpeg re-encode (libx264 preset fast crf 20)** | Clean A/V sync, predictable output, web-streamable. | `-c copy` (fast but desync risk), VideoToolbox (Mac-only, won't work on AWS) |
| **9:16 from 16:9 cut, not from source** | Cuts re-encoding cost roughly in half — second pass only crops, audio just `-c copy`. | Re-encode 9:16 from source twice |
| **Cap deliveries at top 20 clips** | Telegram document upload limit + signal-to-noise (top 20 strongest > all 60 mediocre) | Send all clips |
| **Local Mac M1–M5, S3 from M6** | M-series Mac > t3.medium for video. EC2 burns $10–30/mo. $100 credit lasts longer if saved for M6/M7. | EC2 from day 1, Hetzner |
| **Manual X posting before automation** | Validate clip quality before paying $200/mo X API or risking ToS via browser auto. | X API Basic now, Selenium |
| **9:16 + 16:9 both** | 9:16 for Reels/Shorts/TikTok feed previews; 16:9 for X timeline + YouTube. | Either alone |
| **ASS burned-in subtitles, CapCut style** | Soft subs invisible in feed previews; burned is the standard. Word-level highlight is proven retention pattern. | Soft subs, sentence-at-a-time |
| **Auto-cleanup on success, keep on failure** | Zero disk after success; retries skip downloads. | Always-keep wastes user's tight 90GB |
| **SQLite, single worker** | Solo project, premature complexity. | Postgres + Redis + Celery |
| **Python 3.12** | python-telegram-bot v22 + modern type hints. | System 3.9.6 (too old) |

---

## 9. Conventions & Style

- **Python 3.12+**, type hints on signatures.
- **Black** formatter, **ruff** linter, defaults.
- `snake_case` files/funcs/vars; `PascalCase` classes; `UPPER_SNAKE` constants.
- One responsibility per module.
- `logging` (no `print` in prod paths).
- All paths via `pathlib.Path` rooted at project root.
- Configurable values centralized in `config.py`.
- Secrets via `python-dotenv`, `.env` gitignored.
- Conventional commits: `feat:`, `fix:`, `chore:`, `refactor:`.

---

## 10. Anti-Patterns / "Don't Do This"

- ❌ No paid services unless user explicitly raises it.
- ❌ No automating X posting yet.
- ❌ No EC2 deploy until M4–M6 are done.
- ❌ No stable yt-dlp from PyPI. Always master from git.
- ❌ No `-c copy` for FFmpeg cuts. Re-encode (A/V sync matters more than 25s saved).
- ❌ No Whisper local. Slow on CPU, defeats Deepgram.
- ❌ No Celery/Redis/Postgres until SQLite proves insufficient.
- ❌ No `# comments` in command blocks pasted to user (zsh issue).
- ❌ No suggesting cookies for yt-dlp unless age-restricted videos appear.
- ❌ No premature refactoring. End-to-end first, polish later.
- ❌ No TypeScript/Node rewrites.
- ❌ No bare `python` command in instructions when venv is needed — always include `source .venv/bin/activate` first.

---

## 11. My Working Style & Preferences

(Inferred from a long debugging session; user can correct.)

- **Code-first, explanation-second.** Wants concrete code, not theory.
- **Pragmatic over perfect.** "Get it working" beats "build it right."
- **Appreciates honest pushback.** Pushed back on premature AWS deploy of M1; user agreed.
- **Skill level:** comfortable with Python concepts and MVPs; learning curve on FFmpeg, MediaPipe, ASS subs — explain when those come up.
- **macOS terminal experience:** intermediate. Loses venv after session restore — remind to reactivate.
- **Tendency to take shortcuts** ("ditch subtitles", "deploy now") — push back when shortcuts hurt the goal.
- **Solo founder mindset.** Wants real product earning money on X.
- **Prefers full file rewrites over diffs.**
- **Likes structured responses** with tables for plans, tight prose otherwise.
- **Frustration tolerance:** moderate. After several failures, suggest a clean working path forward, not more debugging.

---

## 12. Open Questions & Pending Decisions

| Question | Options | Leaning |
|---|---|---|
| Is naive 9:16 center-crop acceptable, or do we need M5 first? | Acceptable / unacceptable | TBD — awaiting user feedback after watching clips |
| Subtitle font for M4 | Inter Black, Montserrat Black, Bebas Neue | TBD — A/B on first batch |
| Caption styles in MVP | `highlighted` + `minimalist` only, or all 5 | Confirmed: `highlighted` + `minimalist` |
| Multi-speaker 9:16 (M5) | Pick loudest, split-screen, fallback to center | TBD on real footage |
| Caption hook style | Question / statement / quote | A/B on first 20 posted |
| FFmpeg cut speedup needed? | `-preset ultrafast`, parallel cuts, GPU encode | Hold until scaling demands it |
| Reference X accounts for benchmark | TBD | User to share favorites |
| When to switch transcripts to chunking | When podcasts >5 hours? | Not needed — Deepgram handles full files |

---

## 13. External Context

### API keys (in `.env`, gitignored)

- `TG_BOT_TOKEN` — from @BotFather. Was revoked + regenerated once after accidental exposure.
- `DEEPGRAM_API_KEY` — Nova-3, $200 credit, no card. https://console.deepgram.com
- `GEMINI_API_KEY` — 2.5 Flash-Lite, free tier. https://aistudio.google.com/apikey
- `GROQ_API_KEY` — legacy, optional, no longer used.
- `COOKIES_FROM_BROWSER` — currently unset. Re-enable for age-restricted videos.

### AWS
- $100 credit, untouched. First use planned for M6 (S3).
- Region likely `us-east-1` or `ap-south-1` (India proximity). TBD.

### Reference projects
- **ClipsAI** — https://github.com/ClipsAI/clipsai (Apache-2.0, similar architecture, good reference)
- **Vugola** — paid SaaS, $9/$29/$99/mo. Spec reference for caption styles + features.
- **AutoFlip** (Google) — speaker-aware reframing, M5 reference
- **CapCut** — visual reference for M4 subtitle style

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
| Viral clip | 30–120s self-contained moment that hooks viewers in <3s and ends on a punchline |
| 9:16 | Vertical 1080×1920 — Reels/Shorts/TikTok |
| 16:9 | Horizontal 1920×1080 — X timeline / YouTube |
| Hook | First 1–3s of a clip; determines retention |
| ASS | Advanced SubStation Alpha subtitle format with styling |
| Burned-in subs | Rendered into video pixels (vs separate soft subs) |
| Naive center-crop | M3 9:16 cropping — middle vertical strip of 16:9. Cheap but cuts off off-center speakers |
| Speaker-aware crop | M5 — MediaPipe face-track + dynamic crop window pan |
| Active speaker detection | Per-frame ID of which face is talking, for smart crop |
| Virality score | Gemini-assigned 0–10 score per clip |
| Word-level timestamps | Start/end time per word (Deepgram output), needed for word-highlighted subs |
| CapCut style | TikTok subtitle look: large bold sans-serif, white + black stroke, current word in yellow, lower-third |
| Credit line | "🎙 Channel Name" appended to caption |
| Deno | JS runtime that yt-dlp now requires for YouTube signature challenges |
| Stopgap release | yt-dlp 2026.3.17 — partial YouTube fix; cookies make it worse |
| `-c copy` (FFmpeg) | Stream copy without re-encoding. Fast but causes A/V desync at non-keyframe cuts. We don't use it. |
| `libx264 preset fast crf 20` | Our re-encode settings: software H.264, balanced speed, visually lossless quality |

---

## 🔁 Maintenance Ritual

After every dev session, update:
1. **§4 What Is Built** — append what now works
2. **§5 What Is In Progress** — replace with current task
3. **§7 Known Bugs** — add new, mark resolved
4. **§12 Open Questions** — close resolved, add new
5. **Last Updated** date at top, bump version

Treat as production code: accurate, terse, current.

---

*End of brain v0.4.*
