"""Central configuration. Loads .env and validates required keys."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === API Keys ===
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # legacy, optional

# === YouTube auth (only needed for age-restricted videos) ===
COOKIES_FROM_BROWSER = os.environ.get("COOKIES_FROM_BROWSER")  # safari, chrome, firefox, edge, brave
COOKIES_FILE = os.environ.get("COOKIES_FILE")  # path to cookies.txt

# === Paths ===
PROJECT_ROOT = Path(__file__).parent.resolve()
WORK_DIR = PROJECT_ROOT / "workdir"
WORK_DIR.mkdir(exist_ok=True)

# === Audio settings ===
AUDIO_BITRATE = "64k"
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# === Legacy (Groq) — unused with Deepgram ===
GROQ_MAX_FILE_BYTES = 24 * 1024 * 1024
CHUNK_DURATION_SEC = 600


def validate() -> None:
    """Fail fast on missing required keys at startup."""
    missing = []
    if not TG_BOT_TOKEN:
        missing.append("TG_BOT_TOKEN")
    if not DEEPGRAM_API_KEY:
        missing.append("DEEPGRAM_API_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            f"Add them to .env."
        )
