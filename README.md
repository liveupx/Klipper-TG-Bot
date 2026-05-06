# YT Clipper Bot — Milestone 1

A Telegram bot that downloads a YouTube podcast and returns the transcript with word-level timestamps. This is the foundation; clip cutting, captions, and 9:16 reframing come in later milestones.

---

## What you need before starting

| | |
|---|---|
| Python | **3.11+** ([install](https://www.python.org/downloads/)) |
| FFmpeg | system binary, must be in `PATH` |
| Groq API key | Free at https://console.groq.com/keys |
| Telegram bot token | Free, from BotFather (steps below) |

---

## Setup steps (do these once)

### 1. Create your Telegram bot

1. Open Telegram, search for **`@BotFather`** (the official one, blue checkmark).
2. Send `/newbot`.
3. Pick a **name** (any, e.g. "My Clipper Bot").
4. Pick a **username** — must end in `bot` (e.g. `my_clipper_bot`).
5. BotFather replies with a **token** like `7891234567:AAHxxxxxxxxxxxxxxxxxxxx`.
6. **Copy this token.** You'll paste it into `.env` shortly.
7. (Optional) Send `/setdescription` to BotFather to give it a description.

### 2. Install FFmpeg

| OS | Command |
|---|---|
| **macOS** | `brew install ffmpeg` |
| **Ubuntu / Debian / WSL** | `sudo apt update && sudo apt install -y ffmpeg` |
| **Windows** | Download from https://www.gyan.dev/ffmpeg/builds/ → extract → add `bin/` to PATH |

Verify: `ffmpeg -version` should print version info.

### 3. Set up the project

```bash
cd clipper-bot
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:
```
TG_BOT_TOKEN=7891234567:AAH...        # from BotFather
GROQ_API_KEY=gsk_...                   # from console.groq.com
GEMINI_API_KEY=                        # leave blank for now
```

### 5. Run it

```bash
python main.py
```

You should see: `Bot started. Send a YouTube link in Telegram.`

---

## How to use

1. Open Telegram, find **your bot** (the username you set in step 1).
2. Send `/start` — bot replies with a greeting.
3. Send a YouTube link.
4. Wait. Bot downloads, transcribes, and sends back two files:
   - `<video_id>_transcript.txt` — plain text
   - `<video_id>_transcript.json` — text + segment timestamps + **word-level timestamps** (we'll need these in Milestone 4 for subtitles)

### Test plan — do this in order

1. **Short test (validates pipeline):** any 3–5 min YouTube video. Should finish in under 30 seconds total.
2. **Medium test (validates chunking):** ~30-min video. Triggers Groq's chunking path.
3. **Real test (validates target use case):** an actual 1–2 hour podcast.

If step 1 works but step 2/3 fails, check the bot logs in your terminal — the error and traceback will tell you what's wrong.

---

## Project layout

```
clipper-bot/
├── main.py                    # entry point
├── config.py                  # env loading + settings
├── bot/
│   └── telegram_handler.py    # Telegram message routing
├── worker/
│   ├── download.py            # yt-dlp + FFmpeg postprocess
│   └── transcribe.py          # Groq Whisper + chunking
├── workdir/                   # created at runtime; downloads + transcripts go here (gitignored)
├── requirements.txt
├── .env.example
└── .env                       # your secrets (gitignored)
```

---

## Common problems & fixes

| Problem | Fix |
|---|---|
| `ffmpeg: command not found` | Install FFmpeg (step 2). Restart terminal after. |
| `Missing required env vars` | You forgot to fill `.env`. Re-check step 4. |
| `groq.AuthenticationError` | Bad/missing `GROQ_API_KEY`. Regenerate at console.groq.com. |
| Bot doesn't respond in Telegram | Confirm `python main.py` is still running. Check terminal for errors. |
| `yt-dlp` errors on a video | Some videos are region-locked or private. Try a different one. Update yt-dlp: `pip install -U yt-dlp` |
| Transcription is slow | First call to Groq cold-starts. Subsequent calls are ~200x realtime. |
| Telegram "file too large" when sending transcript back | Shouldn't happen for transcripts (they're tiny). If it does, the bot will tell you. |

---

## What's NOT in Milestone 1

- ❌ Finding viral clips (Milestone 2 — Gemini)
- ❌ Cutting video clips (Milestone 3 — FFmpeg)
- ❌ Burning subtitles (Milestone 4)
- ❌ Speaker-aware 9:16 cropping (Milestone 5)
- ❌ S3 upload (Milestone 6)
- ❌ Auto-posting to X (deferred, manual posting fine)

See `YT_CLIPPER_BOT_v0.1_BRAIN.md` for the full roadmap.

---

## What to test, then come back to me

After Milestone 1 works on a real podcast:

1. Open the resulting `.txt` — does it look accurate? Names, technical terms?
2. Did chunking work cleanly on a 1-hour+ video (no garbled timestamps at chunk boundaries)?
3. How long did the full pipeline take?

Then we move to **Milestone 2**: Gemini reads the JSON and picks 40–60 viral clip ranges with hooks and captions.
