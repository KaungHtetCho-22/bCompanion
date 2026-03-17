# Decisions

## Streaming + latency

- Use WebSocket for single persistent connection (`/ws`).
- Stream assistant tokens to UI via `assistant_delta`.

## TTS flush strategy

Azure TTS has high per-call overhead, so minimizing synth calls matters more than splitting early.

- `sentence`: flush at sentence boundaries (lowest perceived latency if TTS is fast).
- `turn`: flush once per turn (best for reducing TTS overhead).
- `hybrid`: flush once early, then once at end (good compromise).

## SEA-LION models

Model access is key-specific. Always list available models for your key and set `SEALION_MODEL` accordingly.

