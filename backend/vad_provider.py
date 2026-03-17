from __future__ import annotations

from dataclasses import dataclass

from .vad_energy import EnergyVad, EnergyVadConfig


@dataclass
class VadEvent:
    speech_start: bool
    speech_end: bool
    score: float


class VadProvider:
    def reset(self) -> None: ...

    def push_pcm16(self, pcm16: bytes) -> VadEvent: ...


class EnergyVadProvider(VadProvider):
    def __init__(self) -> None:
        self._vad = EnergyVad(EnergyVadConfig())

    def reset(self) -> None:
        self._vad.reset()

    def push_pcm16(self, pcm16: bytes) -> VadEvent:
        speech_start, speech_end, rms = self._vad.push(pcm16)
        return VadEvent(speech_start=speech_start, speech_end=speech_end, score=rms)


class SileroVadLiteProvider(VadProvider):
    """
    Optional server VAD using silero-vad-lite (no torch).

    Expects 16k mono PCM16 input. Internally feeds 512-sample float windows.
    """

    def __init__(self) -> None:
        try:
            from silero_vad_lite import SileroVADLite  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("silero_vad_lite not installed") from e

        self._vad = SileroVADLite()
        self._buf = bytearray()
        self._in_speech = False
        self._start_hits = 0
        self._end_hits = 0
        self._start_prob = 0.5
        self._end_prob = 0.35
        self._start_frames = 2
        self._end_frames = 10

    def reset(self) -> None:
        self._buf.clear()
        self._in_speech = False
        self._start_hits = 0
        self._end_hits = 0

    def push_pcm16(self, pcm16: bytes) -> VadEvent:
        self._buf.extend(pcm16)
        speech_start = False
        speech_end = False
        last_prob = 0.0

        # 512 samples * 2 bytes
        frame_bytes = 1024
        while len(self._buf) >= frame_bytes:
            frame = self._buf[:frame_bytes]
            del self._buf[:frame_bytes]
            floats = _pcm16le_to_float32(frame)
            last_prob = float(self._vad(floats))

            if not self._in_speech:
                if last_prob >= self._start_prob:
                    self._start_hits += 1
                else:
                    self._start_hits = 0
                if self._start_hits >= self._start_frames:
                    self._in_speech = True
                    self._end_hits = 0
                    speech_start = True
            else:
                if last_prob <= self._end_prob:
                    self._end_hits += 1
                else:
                    self._end_hits = 0
                if self._end_hits >= self._end_frames:
                    self._in_speech = False
                    self._start_hits = 0
                    speech_end = True

        return VadEvent(speech_start=speech_start, speech_end=speech_end, score=last_prob)


def _pcm16le_to_float32(pcm16le: bytes) -> list[float]:
    out: list[float] = []
    for i in range(0, len(pcm16le), 2):
        v = int.from_bytes(pcm16le[i : i + 2], "little", signed=True)
        out.append(v / 32768.0)
    return out

