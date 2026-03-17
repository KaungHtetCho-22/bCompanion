# Process log

## 2026-03-17

- Scaffolded backend + frontend prototype (FastAPI WebSocket + single-page React).
- Added persona switching + history windowing.
- Implemented SEA-LION streaming via OpenAI-compatible client with model fallback.
- Implemented Azure TTS (Burmese voice) and browser WAV playback.
- Added latency instrumentation:
  - `llm_first_token_ms`, `llm_tokens`
  - `tts_calls`, `tts_total_ms`
- Tuned TTS flushing strategies:
  - `TTS_FLUSH_MODE=turn` (1 call, lowest overhead, speaks at end)
  - `TTS_FLUSH_MODE=hybrid` (1 early chunk + final chunk)

## Current working state

- Text chat works end-to-end with real LLM + real TTS.
- Audio input now sends `audio_meta` and prefers frontend WAV conversion; backend can ffmpeg-decode webm/opus. Real STT is not wired yet.
- Audio input now has a first-pass ElevenLabs Scribe v2 Realtime STT implementation (expects WAV PCM16 mono 16k).
- Added true streaming mic mode with both client-side and server-side VAD (energy-based) over WebSocket.

## Security note

- Treat `.env` as sensitive and never paste keys into chat/logs.
