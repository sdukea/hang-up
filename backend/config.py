import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


GNANI_API_KEY = _env("GNANI_API_KEY")

STT_URL = "wss://api.vachana.ai/stt/v3/stream"
STT_MODEL = "prisma-v3.0"
STT_LANG = _env("STT_LANG", "hi-IN")
STT_SAMPLE_RATE = 16000
STT_MIN_SILENCE_MS = "500"
STT_MAX_SPEECH_S = "12.0"
STT_PARTIALS = True
# Words a fake officer is likely to say (Prisma v3.0 `x-keyterms`, max 200).
STT_KEYTERMS = [
    "CBI", "police", "digital arrest", "arrest warrant", "OTP", "KYC", "customs", "parcel",
    "courier", "Aadhaar", "PAN", "UPI", "RBI", "safe account", "money laundering", "Dadi",
    "madam", "inspector", "officer", "account", "badge", "bank", "दादी", "Dadi ji", "ओटीपी",
]

TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
TTS_SSE_URL = "https://api.vachana.ai/api/v1/tts/sse"
TTS_MODEL = "timbre-v2.5"
TTS_VOICE = "Chitra"
DADI_VOICE = _env("DADI_VOICE", "Chitra")
DADI_SPEED = float(_env("DADI_SPEED", "1.0"))
PAPPU_VOICE = _env("PAPPU_VOICE", "Vikrant")

# Any OpenAI-compatible chat completions API.
LLM_BASE_URL = _env("LLM_BASE_URL")
LLM_API_KEY = _env("LLM_API_KEY")
LLM_MODEL = _env("LLM_MODEL")
LLM_FALLBACK_MODEL = _env("LLM_FALLBACK_MODEL")
LLM_REASONING_EFFORT = _env("LLM_REASONING_EFFORT")

DATA_DIR = Path(_env("DATA_DIR") or ROOT / "data")
S3_BUCKET = _env("S3_BUCKET")
S3_ENDPOINT_URL = _env("S3_ENDPOINT_URL")
S3_ACCESS_KEY_ID = _env("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = _env("S3_SECRET_ACCESS_KEY")
S3_REGION = _env("S3_REGION", "auto")

# Limits for a public URL: every request spends speech credits or LLM tokens.
MAX_SESSION_SECONDS = int(_env("MAX_SESSION_SECONDS", "240"))
MAX_LISTEN_SESSIONS = int(_env("MAX_LISTEN_SESSIONS", "6"))
GAMES_PER_IP_PER_HOUR = int(_env("GAMES_PER_IP_PER_HOUR", "20"))


def require_key() -> str:
    if not GNANI_API_KEY:
        raise RuntimeError("GNANI_API_KEY is not set. Copy .env.example to .env and add your key.")
    return GNANI_API_KEY
