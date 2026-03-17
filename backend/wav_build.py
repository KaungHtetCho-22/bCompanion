from __future__ import annotations

import io
import wave


def pcm16_to_wav(pcm16: bytes, *, sample_rate: int, channels: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)
    return buf.getvalue()

