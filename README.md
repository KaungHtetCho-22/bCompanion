# bCompanion (Myanmar AI Companion)

A Burmese voice-to-voice AI companion that runs in the browser (React) with a FastAPI WebSocket backend.

This repo prioritizes “talk naturally” UX:
- mic capture (record→send or true streaming)
- VAD (client or server) for end-of-speech detection
- STT → LLM → TTS pipeline
- live token streaming to the UI
- latency metrics visible in the UI

## Docs / tracking

- `docs/INDEX.md` — docs entry point
- `docs/WS_PROTOCOL.md` — WebSocket protocol (including streaming audio)
- `Claude.md` — original product spec we implemented from

## Project structure

```
backend/
  main.py            FastAPI app + WebSocket handler
  pipeline.py        STT→LLM→TTS orchestration + metrics
  stt.py             STT for record→send WAV
  stt_realtime.py    STT streaming session (for streamed mic audio)
  sealion.py         SEA-LION streaming client (OpenAI-compatible)
  tts.py             Azure TTS (WAV output)
  audio_decode.py    ffmpeg decode fallback (webm/opus → WAV)
  vad_provider.py    server VAD backends (energy or silero-vad-lite)
  vad_energy.py      lightweight energy VAD
  stream_state.py    streaming session state
frontend/
  index.html         single-file React UI (no build step)
docs/
  ...
```

## Quickstart (mock mode)

Mock mode runs without real provider keys.

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

./.venv/bin/uvicorn backend.main:app --reload --port 8000
python3 -m http.server 3000 --directory frontend
```

Open `http://127.0.0.1:3000` (don’t use `0.0.0.0` in the browser URL).

## Run with real providers

1) Create `.env`:
```bash
cp .env.example .env
```

2) Fill keys in `.env` and set:
- `USE_MOCK_SERVICES=0`

3) Install the provider deps you need:
```bash
./.venv/bin/pip install -r requirements-llm.txt -r requirements-tts.txt -r requirements-stt.txt
```

4) Start backend + frontend (same as mock mode).

## Frontend mic modes

In the UI, the mic button supports:

- `Record → send`: records in the browser, then sends one blob (WAV preferred).
- `Stream + client VAD`: streams PCM frames; browser decides end-of-speech.
- `Stream + server VAD`: streams PCM frames; backend VAD decides end-of-speech.

## Audio formats

- Frontend tries to convert mic audio to `audio/wav` (PCM16 mono 16k) before sending.
- If conversion fails, it sends `audio/webm;codecs=opus`; backend can decode to WAV if `ffmpeg` is installed.

## VAD options (server-side)

Default server VAD is lightweight energy-based.

Optional higher-quality VAD without torch:
```bash
./.venv/bin/pip install -r requirements-vad-lite.txt
```

Then set in `.env`:
- `VAD_BACKEND=silero_vad_lite`

## SEA-LION model selection

Model access is key-specific. If you see “Invalid model name” or “key not allowed”, list available models:

```bash
./.venv/bin/python scripts/list_sealion_models.py
```

Then set `.env`:
- `SEALION_MODEL=...`
- `SEALION_FALLBACK=...`

## Latency metrics (UI)

The UI shows:
- `stt_ms` — STT time
- `llm_first_token_ms` — time to first LLM token
- `tts_total_ms` and `tts_calls` — Azure TTS time and number of synth calls

Useful knobs in `.env`:
- `LLM_MAX_TOKENS` (smaller is faster)
- `TTS_FLUSH_MODE` (`turn` / `hybrid` / `sentence`)

