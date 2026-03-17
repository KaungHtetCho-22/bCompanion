from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

from .config import (
    LATENCY_FAIL_MS,
    LATENCY_WARN_MS,
    MAX_HISTORY_TURNS,
    TTS_FLUSH_MAX_CHARS,
    TTS_FLUSH_MAX_DELAY_MS,
    TTS_FLUSH_MODE,
    TTS_TIMEOUT_MS,
)
from .personas import ANTI_ROBOTIC_RULES, get_fewshot_examples, get_persona
from .sealion import stream_response
from .stt import transcribe
from .tts import synthesize


def build_messages(persona_id: str, history: list[dict[str, str]], user_input: str) -> list[dict[str, str]]:
    persona_prompt = get_persona(persona_id) + "\n\n" + ANTI_ROBOTIC_RULES
    messages: list[dict[str, str]] = [{"role": "system", "content": persona_prompt}]
    messages += get_fewshot_examples(persona_id)
    messages += history[-MAX_HISTORY_TURNS:]
    messages.append({"role": "user", "content": user_input})
    return messages


def is_sentence_boundary(text: str) -> bool:
    stripped = text.rstrip()
    return any(stripped.endswith(p) for p in ["။", ".", "?", "!"])


def _split_for_tts_forced_flush(text: str) -> tuple[str | None, str]:
    if not text.strip():
        return None, text

    separators = ["။", "၊", ".", "?", "!", " "]
    last_idx = -1
    for sep in separators:
        idx = text.rfind(sep)
        if idx > last_idx:
            last_idx = idx

    if last_idx <= 0:
        return None, text

    cut = last_idx + 1
    return text[:cut], text[cut:]


async def run_text_turn(
    *,
    text: str,
    persona_id: str,
    history: list[dict[str, str]],
) -> tuple[str, list[bytes], dict[str, float]]:
    audio_chunks: list[bytes] = []
    full_text = ""
    final_metrics: dict[str, float] = {}

    async for kind, payload in stream_text_turn(text=text, persona_id=persona_id, history=history):
        if kind == "audio":
            audio_chunks.append(payload)  # type: ignore[arg-type]
        elif kind == "done":
            full_text = (payload or {}).get("text", "")
            final_metrics = (payload or {}).get("metrics", {})

    return full_text, audio_chunks, final_metrics


async def stream_text_turn(
    *,
    text: str,
    persona_id: str,
    history: list[dict[str, str]],
) -> AsyncGenerator[tuple[str, object], None]:
    t0 = time.monotonic()
    messages = build_messages(persona_id, history, text)

    sentence_buffer = ""
    full_response = ""
    t_first_token: float | None = None
    llm_tokens = 0
    tts_calls = 0
    tts_total_ms = 0.0
    t_last_flush = time.monotonic()
    hybrid_flushed = False

    yield ("status", "llm_start")
    async for token in stream_response(messages):
        if t_first_token is None:
            t_first_token = time.monotonic()
            yield ("status", "llm_first_token")

        full_response += token
        sentence_buffer += token
        llm_tokens += 1
        yield ("token", token)

        if TTS_FLUSH_MODE == "turn":
            continue
        if TTS_FLUSH_MODE == "hybrid" and hybrid_flushed:
            continue

        should_flush = False
        forced_flush = False
        if is_sentence_boundary(sentence_buffer):
            should_flush = True
        elif len(sentence_buffer) >= TTS_FLUSH_MAX_CHARS:
            should_flush = True
            forced_flush = True
        elif (time.monotonic() - t_last_flush) * 1000.0 >= TTS_FLUSH_MAX_DELAY_MS and sentence_buffer.strip():
            should_flush = True
            forced_flush = True

        if should_flush:
            yield ("status", "tts_start")
            try:
                tts_calls += 1
                t_tts0 = time.monotonic()
                chunk_text = sentence_buffer
                remainder = ""
                if forced_flush:
                    split, remainder = _split_for_tts_forced_flush(sentence_buffer)
                    if split is None:
                        tts_calls -= 1
                        yield ("status", "tts_deferred")
                        continue
                    chunk_text = split

                audio = await asyncio.wait_for(synthesize(chunk_text), timeout=(TTS_TIMEOUT_MS / 1000.0))
                tts_total_ms += (time.monotonic() - t_tts0) * 1000.0
                yield ("audio", audio)
            except Exception as e:
                yield ("error", f"tts_failed: {type(e).__name__}: {e}")
            sentence_buffer = remainder
            t_last_flush = time.monotonic()
            if TTS_FLUSH_MODE == "hybrid":
                hybrid_flushed = True

    if sentence_buffer.strip():
        yield ("status", "tts_start")
        try:
            tts_calls += 1
            t_tts0 = time.monotonic()
            audio = await asyncio.wait_for(synthesize(sentence_buffer), timeout=(TTS_TIMEOUT_MS / 1000.0))
            tts_total_ms += (time.monotonic() - t_tts0) * 1000.0
            yield ("audio", audio)
        except Exception as e:
            yield ("error", f"tts_failed: {type(e).__name__}: {e}")

    t_total_ms = (time.monotonic() - t0) * 1000.0
    llm_first_token_ms = ((t_first_token - t0) * 1000.0) if t_first_token is not None else None
    metrics = {
        "total_ms": t_total_ms,
        "llm_first_token_ms": llm_first_token_ms,
        "llm_tokens": llm_tokens,
        "tts_calls": tts_calls,
        "tts_total_ms": tts_total_ms,
        "warn": float(t_total_ms > LATENCY_WARN_MS),
        "fail": float(t_total_ms > LATENCY_FAIL_MS),
    }
    yield ("done", {"text": full_response, "metrics": metrics})


async def run_audio_turn(
    *,
    audio_bytes: bytes,
    persona_id: str,
    history: list[dict[str, str]],
    mime_type: str | None = None,
) -> tuple[str, str, list[bytes], dict[str, float]]:
    t0 = time.monotonic()
    transcript = await transcribe(audio_bytes, mime_type=mime_type)
    t_stt_ms = (time.monotonic() - t0) * 1000.0

    reply, audio_chunks, metrics = await run_text_turn(text=transcript, persona_id=persona_id, history=history)
    metrics["stt_ms"] = t_stt_ms
    return transcript, reply, audio_chunks, metrics
