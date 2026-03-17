from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass

from .config import ELEVENLABS_API_KEY, ELEVENLABS_STT_MODEL_ID, STT_LANGUAGE_CODE, USE_MOCK_SERVICES


class SttRealtimeError(RuntimeError):
    pass


@dataclass
class RealtimeTranscript:
    partial: str = ""
    committed_parts: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.committed_parts is None:
            self.committed_parts = []

    def committed_text(self) -> str:
        return " ".join([p.strip() for p in self.committed_parts if p and p.strip()]).strip()

    def best_text(self) -> str:
        committed = self.committed_text()
        if committed:
            return committed
        return (self.partial or "").strip()


class ElevenLabsRealtimeSttSession:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        audio_format: str = "pcm_16000",
        commit_strategy: str = "manual",
        previous_text: str | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.audio_format = audio_format
        self.commit_strategy = commit_strategy
        self.previous_text = previous_text

        self._ws = None
        self._rx_task: asyncio.Task | None = None
        self._closed = False
        self._transcript = RealtimeTranscript()
        self._committed_event = asyncio.Event()
        self._session_started = asyncio.Event()
        self._last_error: str | None = None
        self._sent_any_audio = False

    @property
    def transcript(self) -> RealtimeTranscript:
        return self._transcript

    async def connect(self) -> None:
        if USE_MOCK_SERVICES or not ELEVENLABS_API_KEY:
            raise SttRealtimeError("ELEVENLABS_API_KEY not set or USE_MOCK_SERVICES=1")

        import websockets  # type: ignore

        qs = (
            f"model_id={ELEVENLABS_STT_MODEL_ID}"
            f"&language_code={STT_LANGUAGE_CODE}"
            f"&audio_format={self.audio_format}"
            f"&commit_strategy={self.commit_strategy}"
            f"&include_timestamps=false"
            f"&include_language_detection=false"
        )
        url = f"wss://api.elevenlabs.io/v1/speech-to-text/realtime?{qs}"
        headers = {"xi-api-key": ELEVENLABS_API_KEY}

        self._ws = await _ws_connect(websockets, url, headers=headers)
        self._rx_task = asyncio.create_task(self._rx_loop())

        await asyncio.wait_for(self._session_started.wait(), timeout=10.0)

    async def send_pcm16(self, pcm16_bytes: bytes) -> None:
        if self._closed:
            return
        if not self._ws:
            raise SttRealtimeError("session not connected")
        if not pcm16_bytes:
            return

        msg: dict = {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(pcm16_bytes).decode("ascii"),
            "sample_rate": self.sample_rate,
        }
        if not self._sent_any_audio and self.previous_text:
            msg["previous_text"] = self.previous_text
        self._sent_any_audio = True
        await self._ws.send(json.dumps(msg))

    async def commit_and_wait(self, *, timeout_s: float = 20.0) -> str:
        if self._closed:
            raise SttRealtimeError("session closed")
        if not self._ws:
            raise SttRealtimeError("session not connected")

        # Commit by sending a short silence chunk with commit=true. (API reference supports `commit` on input_audio_chunk.)
        silence = b"\x00\x00" * int(self.sample_rate * 0.2)
        msg = {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(silence).decode("ascii"),
            "sample_rate": self.sample_rate,
            "commit": True,
        }
        await self._ws.send(json.dumps(msg))

        self._committed_event.clear()
        try:
            await asyncio.wait_for(self._committed_event.wait(), timeout=timeout_s)
        except asyncio.TimeoutError as e:
            raise TimeoutError("STT timeout waiting for committed transcript") from e

        if self._last_error:
            raise SttRealtimeError(self._last_error)

        return self._transcript.best_text()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._ws:
                await self._ws.close()
        finally:
            if self._rx_task:
                self._rx_task.cancel()
                with contextlib.suppress(Exception):
                    await self._rx_task

    async def _rx_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                t = msg.get("message_type")
                if t == "session_started":
                    self._session_started.set()
                elif t == "partial_transcript":
                    self._transcript.partial = msg.get("text") or ""
                elif t == "committed_transcript":
                    text = msg.get("text") or ""
                    if text.strip():
                        self._transcript.committed_parts.append(text)
                    self._committed_event.set()
                elif t and t.endswith("_error"):
                    self._last_error = msg.get("message") or msg.get("detail") or f"STT error ({t})"
                    self._committed_event.set()
                elif t == "session_ended":
                    self._committed_event.set()
                    return
        except Exception as e:
            self._last_error = f"STT rx failed: {type(e).__name__}: {e}"
            self._committed_event.set()


async def _ws_connect(websockets_module, url: str, *, headers: dict):
    kwargs = {"max_size": 8 * 1024 * 1024}
    try:
        return await websockets_module.connect(url, additional_headers=headers, **kwargs)
    except TypeError:
        return await websockets_module.connect(url, extra_headers=headers, **kwargs)


import contextlib  # placed at end to avoid unused warnings in earlier exceptions

