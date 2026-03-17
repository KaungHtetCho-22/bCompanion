# WebSocket protocol

## JSON messages (client → server)

- `switch_persona` — `{ type, persona_id }`
- `text` — `{ type, text }`
- `audio_meta` — `{ type, mime }` (non-streaming recorded chunk path)

### Streaming audio

- `audio_stream_start` — `{ type, format, sample_rate, channels, vad_mode }`
  - `format`: `pcm_s16le`
  - `vad_mode`: `client` or `server`
- `audio_stream_end` — `{ type }` (manual end-of-turn; also sent by client VAD)

## Binary frames (client → server)

When streaming is active (after `audio_stream_start`), each binary frame is raw PCM:

- `Int16Array` little-endian (`pcm_s16le`), mono 16k recommended.

## Server → client

- `status` — `{ type:"status", value }`
- `error` — `{ type:"error", message }`
- `transcript` — `{ type:"transcript", text }`
- `assistant_delta` — `{ type:"assistant_delta", text }`
- `assistant_text` — `{ type:"assistant_text", text }`
- `metrics` — `{ type:"metrics", data }`

