from __future__ import annotations

import math
from dataclasses import dataclass


def rms_int16(pcm16: bytes) -> float:
    if not pcm16:
        return 0.0
    n = len(pcm16) // 2
    if n == 0:
        return 0.0
    s = 0.0
    for i in range(0, n * 2, 2):
        v = int.from_bytes(pcm16[i : i + 2], "little", signed=True)
        s += (v / 32768.0) ** 2
    return math.sqrt(s / n)


@dataclass
class EnergyVadConfig:
    start_rms: float = 0.012
    end_rms: float = 0.009
    start_frames: int = 3
    end_frames: int = 12


class EnergyVad:
    def __init__(self, cfg: EnergyVadConfig | None = None) -> None:
        self.cfg = cfg or EnergyVadConfig()
        self._speech = False
        self._start_hits = 0
        self._end_hits = 0

    @property
    def in_speech(self) -> bool:
        return self._speech

    def reset(self) -> None:
        self._speech = False
        self._start_hits = 0
        self._end_hits = 0

    def push(self, pcm16: bytes) -> tuple[bool, bool, float]:
        """
        Returns (speech_start, speech_end, rms).
        """
        r = rms_int16(pcm16)
        speech_start = False
        speech_end = False

        if not self._speech:
            if r >= self.cfg.start_rms:
                self._start_hits += 1
            else:
                self._start_hits = 0
            if self._start_hits >= self.cfg.start_frames:
                self._speech = True
                self._end_hits = 0
                speech_start = True
        else:
            if r <= self.cfg.end_rms:
                self._end_hits += 1
            else:
                self._end_hits = 0
            if self._end_hits >= self.cfg.end_frames:
                self._speech = False
                self._start_hits = 0
                speech_end = True

        return speech_start, speech_end, r

