from __future__ import annotations

import asyncio
import base64
import json

from .config import ELEVENLABS_API_KEY, USE_MOCK_SERVICES
from .config import ELEVENLABS_STT_MODEL_ID, STT_LANGUAGE_CODE
from .wav_util import WavError, wav_info_and_pcm16


async def transcribe(audio_bytes: bytes, *, mime_type: str | None = None) -> str:
    if USE_MOCK_SERVICES or not ELEVENLABS_API_KEY:
        suffix = f" ({mime_type})" if mime_type else ""
        return f"ဟေ့—ငါစမ်းနေတယ် (mock STT){suffix}"

    if mime_type and not mime_type.startswith("audio/wav"):
        raise RuntimeError(f"STT expects wav after decode, got mime_type={mime_type}")

    sample_rate, channels, pcm16 = wav_info_and_pcm16(audio_bytes)
    if channels != 1:
        raise RuntimeError(f"STT expects mono wav, got channels={channels}")

    # ElevenLabs Scribe v2 Realtime (WebSocket). We send audio in ~1s chunks.
    # Ref: https://elevenlabs.io/docs/api-reference/speech-to-text/convert-realtime
    import websockets  # type: ignore

    qs = (
        f"model_id={ELEVENLABS_STT_MODEL_ID}"
        f"&language_code={STT_LANGUAGE_CODE}"
        f"&audio_format=pcm_16000"
        f"&commit_strategy=manual"
    )
    url = f"wss://api.elevenlabs.io/v1/speech-to-text/realtime?{qs}"

    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    async with _ws_connect(websockets, url, headers=headers) as ws:
        # Wait for session_started
        await _recv_until(ws, wanted={"session_started"}, timeout_s=10.0)

        bytes_per_second = sample_rate * 2  # mono * int16
        if sample_rate != 16000:
            raise RuntimeError(f"expected 16000Hz wav (got {sample_rate}); enable frontend WAV conversion")

        offset = 0
        while offset < len(pcm16):
            chunk = pcm16[offset : offset + bytes_per_second]
            offset += len(chunk)
            commit = offset >= len(pcm16)
            msg = {
                "message_type": "input_audio_chunk",
                "audio_base_64": base64.b64encode(chunk).decode("ascii"),
                "sample_rate": sample_rate,
                "commit": commit,
            }
            await ws.send(json.dumps(msg))

        # Wait for committed transcript
        transcript = await _recv_transcript(ws, timeout_s=20.0)
        return transcript.strip() or "(no transcript)"


def _ws_connect(websockets_module, url: str, *, headers: dict) :
    kwargs = {"max_size": 8 * 1024 * 1024}
    try:
        return websockets_module.connect(url, additional_headers=headers, **kwargs)
    except TypeError:
        return websockets_module.connect(url, extra_headers=headers, **kwargs)


async def _recv_until(ws, *, wanted: set[str], timeout_s: float) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"STT timeout waiting for {wanted}")
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        msg = json.loads(raw)
        if msg.get("message_type") in wanted:
            return msg


async def _recv_transcript(ws, *, timeout_s: float) -> str:
    deadline = asyncio.get_event_loop().time() + timeout_s
    best = ""
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError("STT timeout waiting for transcript")
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        msg = json.loads(raw)
        t = msg.get("message_type")
        if t == "committed_transcript":
            return msg.get("text") or ""
        if t == "partial_transcript":
            best = msg.get("text") or best
        if t and t.endswith("_error"):
            raise RuntimeError(msg.get("message") or msg.get("detail") or "STT error")
        if t == "session_ended":
            return best
