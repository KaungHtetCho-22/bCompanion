# Next steps

## STT (audio → text)

1) Decide audio format and transport:
   - Browser `MediaRecorder` typically produces `audio/webm;codecs=opus`.
   - Many STT APIs prefer WAV/PCM. Both conversion routes now exist:
     - Frontend converts to WAV PCM16 mono 16k (preferred).
     - Backend can decode webm/opus via `ffmpeg` if installed.

2) Wire ElevenLabs Scribe (or alternative STT) behind `backend/stt.py`.
   - Backend now attempts ElevenLabs Scribe v2 Realtime when `ELEVENLABS_API_KEY` is set and `USE_MOCK_SERVICES=0`.
   - Current mode is still “send a recorded chunk”, not true streaming.

3) Add protocol messages:
   - Send audio metadata (mime type, sample rate if available) before audio bytes.

## VAD (turn detection)

- Streaming audio + VAD is implemented (energy-based) for both:
  - client VAD (browser decides end-of-speech)
  - server VAD (backend decides end-of-speech)
- Next improvement: replace energy VAD with Silero VAD (requires `torch`) once ready.
  - Optional no-torch upgrade available via `requirements-vad-lite.txt` and `VAD_BACKEND=silero_vad_lite`.

## Perf

- Keep `LLM_MAX_TOKENS` small, enforce short persona replies.
- Use `TTS_FLUSH_MODE=hybrid` for early audio without many TTS calls.
