from __future__ import annotations

import shutil
import subprocess


class AudioDecodeError(RuntimeError):
    pass


def decode_to_wav_pcm16_mono_16k(audio_bytes: bytes, *, mime_type: str | None, timeout_s: float = 10.0) -> bytes:
    """
    Best-effort decoder for browser-recorded audio (often webm/opus).

    Uses `ffmpeg` if available to produce WAV PCM16 mono 16k.
    """
    if not mime_type:
        raise AudioDecodeError("missing mime_type")

    if mime_type.startswith("audio/wav"):
        return audio_bytes

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioDecodeError("ffmpeg not found (install ffmpeg or enable frontend WAV conversion)")

    args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        "pipe:1",
    ]

    try:
        proc = subprocess.run(
            args,
            input=audio_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        raise AudioDecodeError("ffmpeg decode timeout") from e

    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise AudioDecodeError(f"ffmpeg decode failed: {detail}")

    if not proc.stdout.startswith(b"RIFF"):
        raise AudioDecodeError("ffmpeg output is not WAV/RIFF")

    return proc.stdout

