import os

from dotenv import load_dotenv


load_dotenv(dotenv_path=".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


# API Keys
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
SEALION_API_KEY = os.getenv("SEALION_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# STT Config
STT_LANGUAGE_CODE = os.getenv("STT_LANGUAGE_CODE", "my")
ELEVENLABS_STT_MODEL_ID = os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v2_realtime")

# VAD Config
VAD_BACKEND = os.getenv("VAD_BACKEND", "energy")  # energy | silero_vad_lite

# Behavior
USE_MOCK_SERVICES = _env_bool("USE_MOCK_SERVICES", default=True)

# LLM Config (mirrors Claude.md defaults)
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "150"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.85"))
LLM_TIMEOUT_MS = int(os.getenv("LLM_TIMEOUT_MS", "600"))
LLM_TOKEN_TIMEOUT_MS = int(os.getenv("LLM_TOKEN_TIMEOUT_MS", "2500"))
LLM_FALLBACK_TIMEOUT_MS = int(os.getenv("LLM_FALLBACK_TIMEOUT_MS", "2500"))
SEALION_MODEL = os.getenv("SEALION_MODEL", "aisingapore/Gemma-SEA-LION-v4-27B-IT")
SEALION_FALLBACK = os.getenv("SEALION_FALLBACK", "aisingapore/Llama-SEA-LION-v3-70B-IT")
SEALION_BASE_URL = os.getenv("SEALION_BASE_URL", "https://api.sea-lion.ai/v1")
SEALION_CONNECT_TIMEOUT_MS = int(os.getenv("SEALION_CONNECT_TIMEOUT_MS", "1500"))
SEALION_READ_TIMEOUT_MS = int(os.getenv("SEALION_READ_TIMEOUT_MS", "3000"))

# TTS Config (mirrors Claude.md defaults)
TTS_VOICE = os.getenv("TTS_VOICE", "my-MM-NilarNeural")
TTS_RATE = os.getenv("TTS_RATE", "+5%")
TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")
TTS_TIMEOUT_MS = int(os.getenv("TTS_TIMEOUT_MS", "4000"))
TTS_FLUSH_MAX_CHARS = int(os.getenv("TTS_FLUSH_MAX_CHARS", "240"))
TTS_FLUSH_MAX_DELAY_MS = int(os.getenv("TTS_FLUSH_MAX_DELAY_MS", "5000"))
TTS_FLUSH_MODE = os.getenv("TTS_FLUSH_MODE", "sentence")  # "sentence" | "turn" | "hybrid"

# Pipeline Config
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))
LATENCY_WARN_MS = int(os.getenv("LATENCY_WARN_MS", "700"))
LATENCY_FAIL_MS = int(os.getenv("LATENCY_FAIL_MS", "1000"))
