from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

from .config import (
    LLM_MAX_TOKENS,
    LLM_FALLBACK_TIMEOUT_MS,
    LLM_TOKEN_TIMEOUT_MS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_MS,
    SEALION_API_KEY,
    SEALION_BASE_URL,
    SEALION_CONNECT_TIMEOUT_MS,
    SEALION_READ_TIMEOUT_MS,
    SEALION_FALLBACK,
    SEALION_MODEL,
    USE_MOCK_SERVICES,
)


async def stream_response(messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
    if USE_MOCK_SERVICES or not SEALION_API_KEY:
        text = "အိုကေ နော်—ပြော၊ မင်းဘာလိုချင်တာလဲ"
        for token in _chunk_text(text):
            yield token
        return

    import httpx  # type: ignore
    from openai import AsyncOpenAI  # type: ignore

    timeout = httpx.Timeout(
        connect=(SEALION_CONNECT_TIMEOUT_MS / 1000.0),
        read=(SEALION_READ_TIMEOUT_MS / 1000.0),
        write=10.0,
        pool=10.0,
    )
    http_client = httpx.AsyncClient(timeout=timeout)
    client = AsyncOpenAI(
        api_key=SEALION_API_KEY,
        base_url=SEALION_BASE_URL,
        max_retries=0,
        http_client=http_client,
    )

    async def _stream_model(model: str) -> AsyncGenerator[str, None]:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    try:
        try:
            async for token in _stream_with_timeouts(
                _stream_model(SEALION_MODEL),
                first_token_timeout_ms=LLM_TIMEOUT_MS,
                token_timeout_ms=LLM_TOKEN_TIMEOUT_MS,
            ):
                yield token
            return
        except Exception:
            async for token in _stream_with_timeouts(
                _stream_model(SEALION_FALLBACK),
                first_token_timeout_ms=max(LLM_FALLBACK_TIMEOUT_MS, 1200),
                token_timeout_ms=LLM_TOKEN_TIMEOUT_MS,
            ):
                yield token
    finally:
        await http_client.aclose()


def _chunk_text(text: str, chunk_size: int = 6) -> list[str]:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


async def _stream_with_timeouts(
    gen: AsyncGenerator[str, None], *, first_token_timeout_ms: int, token_timeout_ms: int
) -> AsyncGenerator[str, None]:
    it = gen.__aiter__()
    first_deadline_s = time.monotonic() + (first_token_timeout_ms / 1000.0)

    first = True
    while True:
        try:
            if first:
                remaining = first_deadline_s - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("LLM first-token timeout")
                try:
                    token = await asyncio.wait_for(it.__anext__(), timeout=remaining)
                except asyncio.TimeoutError as e:
                    raise TimeoutError(f"LLM first-token timeout after {first_token_timeout_ms}ms") from e
                first = False
                yield token
            else:
                try:
                    token = await asyncio.wait_for(it.__anext__(), timeout=(token_timeout_ms / 1000.0))
                except asyncio.TimeoutError as e:
                    raise TimeoutError(f"LLM token timeout after {token_timeout_ms}ms") from e
                yield token
        except StopAsyncIteration:
            return
