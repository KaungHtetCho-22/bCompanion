from __future__ import annotations

import io
import wave


class WavError(ValueError):
    pass


def wav_info_and_pcm16(wav_bytes: bytes) -> tuple[int, int, bytes]:
    """
    Returns (sample_rate, channels, pcm16_bytes).

    Expects PCM16 WAV input.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            comp = wf.getcomptype()
            if comp != "NONE":
                raise WavError(f"unsupported compression: {comp}")
            if sample_width != 2:
                raise WavError(f"expected 16-bit PCM, got sampwidth={sample_width}")
            pcm = wf.readframes(wf.getnframes())
            return sample_rate, channels, pcm
    except wave.Error as e:
        raise WavError(f"invalid wav: {e}") from e

