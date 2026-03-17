from __future__ import annotations

import json
from dataclasses import dataclass, field

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .audio_decode import AudioDecodeError, decode_to_wav_pcm16_mono_16k
from .pipeline import run_audio_turn, run_text_turn, stream_text_turn
from .stream_state import AudioStreamConfig, AudioStreamState
from .wav_build import pcm16_to_wav
from .stt_realtime import ElevenLabsRealtimeSttSession, SttRealtimeError


load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class SessionState:
    persona_id: str = "friend"
    history: list[dict[str, str]] = field(default_factory=list)
    audio_mime: str | None = None
    stream: AudioStreamState = field(default_factory=AudioStreamState)
    stt_stream: ElevenLabsRealtimeSttSession | None = None
    stt_send_buf: bytearray = field(default_factory=bytearray)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    state = SessionState()

    async def _finalize_stream_turn(*, reason: str) -> None:
        if not state.stream.active or not state.stream.cfg:
            return
        cfg = state.stream.cfg
        if not state.stream.pcm16 and state.stt_stream is None:
            await ws.send_json({"type": "error", "message": f"stt_failed: empty_audio ({reason})"})
            state.stream.stop()
            return

        await ws.send_json({"type": "status", "value": f"stream_end:{reason}"})

        transcript = ""
        if state.stt_stream is not None:
            await ws.send_json({"type": "status", "value": "stt_stream_commit"})
            try:
                transcript = await state.stt_stream.commit_and_wait(timeout_s=25.0)
            finally:
                await state.stt_stream.close()
                state.stt_stream = None
            state.stream.stop()

            await ws.send_json({"type": "transcript", "text": transcript})
            await ws.send_json({"type": "status", "value": "llm_start"})
            reply, audio_chunks, metrics = await run_text_turn(
                text=transcript, persona_id=state.persona_id, history=state.history
            )
        else:
            wav_bytes = pcm16_to_wav(bytes(state.stream.pcm16), sample_rate=cfg.sample_rate, channels=cfg.channels)
            state.audio_mime = "audio/wav;codec=pcm_s16le;rate=16000;channels=1"
            state.stream.stop()

            await ws.send_json({"type": "status", "value": "stt_start"})
            transcript, reply, audio_chunks, metrics = await run_audio_turn(
                audio_bytes=wav_bytes,
                persona_id=state.persona_id,
                history=state.history,
                mime_type=state.audio_mime,
            )
        await ws.send_json({"type": "transcript", "text": transcript})
        await ws.send_json({"type": "assistant_text", "text": reply})
        await ws.send_json({"type": "metrics", "data": metrics})
        for chunk in audio_chunks:
            await ws.send_bytes(chunk)

        state.history.append({"role": "user", "content": transcript})
        state.history.append({"role": "assistant", "content": reply})

    try:
        while True:
            try:
                message = await ws.receive()
            except RuntimeError as e:
                if 'disconnect message has been received' in str(e):
                    break
                raise

            if message.get("type") == "websocket.disconnect":
                break

            if "text" in message and message["text"] is not None:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "switch_persona":
                    state.persona_id = data.get("persona_id", "friend")
                    state.history.clear()
                    await ws.send_json({"type": "persona", "persona_id": state.persona_id})
                    continue

                if msg_type == "audio_meta":
                    state.audio_mime = data.get("mime")
                    await ws.send_json({"type": "status", "value": "audio_meta_ok"})
                    continue

                if msg_type == "audio_stream_start":
                    cfg = AudioStreamConfig(
                        format=data.get("format") or "pcm_s16le",
                        sample_rate=int(data.get("sample_rate") or 16000),
                        channels=int(data.get("channels") or 1),
                        vad_mode=(data.get("vad_mode") or "server"),
                    )
                    if cfg.format != "pcm_s16le" or cfg.channels != 1 or cfg.sample_rate != 16000:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "stream_start_failed: expected pcm_s16le mono 16k",
                            }
                        )
                        continue
                    state.stream.start(cfg)
                    state.stt_send_buf.clear()
                    state.stt_stream = None
                    try:
                        state.stt_stream = ElevenLabsRealtimeSttSession(sample_rate=cfg.sample_rate)
                        await state.stt_stream.connect()
                        await ws.send_json({"type": "status", "value": "stt_stream_connected"})
                    except Exception as e:
                        state.stt_stream = None
                        await ws.send_json({"type": "status", "value": f"stt_stream_disabled:{type(e).__name__}"})
                    await ws.send_json({"type": "status", "value": f"stream_start:{cfg.vad_mode}"})
                    continue

                if msg_type == "audio_stream_end":
                    if state.stt_stream is not None and state.stt_send_buf:
                        await state.stt_stream.send_pcm16(bytes(state.stt_send_buf))
                        state.stt_send_buf.clear()
                    await _finalize_stream_turn(reason="client_end")
                    continue

                if msg_type == "text":
                    user_text = (data.get("text") or "").strip()
                    if not user_text:
                        continue

                    try:
                        await ws.send_json({"type": "transcript", "text": user_text})
                        full_reply = ""
                        metrics = None
                        async for kind, payload in stream_text_turn(
                            text=user_text, persona_id=state.persona_id, history=state.history
                        ):
                            if kind == "token":
                                await ws.send_json({"type": "assistant_delta", "text": payload})
                            elif kind == "audio":
                                await ws.send_bytes(payload)  # type: ignore[arg-type]
                            elif kind == "status":
                                await ws.send_json({"type": "status", "value": payload})
                            elif kind == "error":
                                await ws.send_json({"type": "error", "message": payload})
                            elif kind == "done":
                                full_reply = (payload or {}).get("text", "")
                                metrics = (payload or {}).get("metrics")
                        await ws.send_json({"type": "assistant_text", "text": full_reply})
                        if metrics is not None:
                            await ws.send_json({"type": "metrics", "data": metrics})
                    except Exception as e:
                        await ws.send_json({"type": "error", "message": f"turn_failed: {type(e).__name__}: {e!r}"})
                        continue

                    state.history.append({"role": "user", "content": user_text})
                    state.history.append({"role": "assistant", "content": full_reply})
                    continue

                await ws.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})
                continue

            if "bytes" in message and message["bytes"] is not None:
                try:
                    audio_bytes: bytes = message["bytes"]

                    if state.stream.active and state.stream.cfg:
                        cfg = state.stream.cfg
                        state.stream.pcm16.extend(audio_bytes)
                        if state.stt_stream is not None:
                            # Aggregate to ~200ms chunks before sending upstream.
                            state.stt_send_buf.extend(audio_bytes)
                            chunk_bytes = 16000 * 2 // 5  # 200ms
                            while len(state.stt_send_buf) >= chunk_bytes:
                                chunk = bytes(state.stt_send_buf[:chunk_bytes])
                                del state.stt_send_buf[:chunk_bytes]
                                await state.stt_stream.send_pcm16(chunk)
                        if cfg.vad_mode == "server":
                            ev = state.stream.vad.push_pcm16(audio_bytes)
                            speech_start, speech_end = ev.speech_start, ev.speech_end
                            if speech_start:
                                await ws.send_json({"type": "status", "value": "vad_speech_start"})
                            if speech_end:
                                await ws.send_json({"type": "status", "value": "vad_speech_end"})
                                if state.stt_stream is not None and state.stt_send_buf:
                                    await state.stt_stream.send_pcm16(bytes(state.stt_send_buf))
                                    state.stt_send_buf.clear()
                                await _finalize_stream_turn(reason="server_vad")
                        continue

                    mime = state.audio_mime
                    if mime and not mime.startswith("audio/wav"):
                        await ws.send_json({"type": "status", "value": "audio_decode_start"})
                        try:
                            audio_bytes = decode_to_wav_pcm16_mono_16k(audio_bytes, mime_type=mime)
                            state.audio_mime = "audio/wav;codec=pcm_s16le;rate=16000;channels=1"
                            await ws.send_json({"type": "status", "value": "audio_decode_ok"})
                        except AudioDecodeError as e:
                            await ws.send_json({"type": "error", "message": f"audio_decode_failed: {e}"})

                    await ws.send_json({"type": "status", "value": "stt_start"})
                    transcript, reply, audio_chunks, metrics = await run_audio_turn(
                        audio_bytes=audio_bytes,
                        persona_id=state.persona_id,
                        history=state.history,
                        mime_type=state.audio_mime,
                    )
                    await ws.send_json({"type": "transcript", "text": transcript})
                    await ws.send_json({"type": "assistant_text", "text": reply})
                    await ws.send_json({"type": "metrics", "data": metrics})
                    for chunk in audio_chunks:
                        await ws.send_bytes(chunk)
                except Exception as e:
                    await ws.send_json({"type": "error", "message": f"turn_failed: {type(e).__name__}: {e!r}"})
                    continue

                state.history.append({"role": "user", "content": transcript})
                state.history.append({"role": "assistant", "content": reply})
                continue

    except WebSocketDisconnect:
        return
