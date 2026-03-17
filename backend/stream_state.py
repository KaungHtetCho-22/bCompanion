from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import VAD_BACKEND
from .vad_provider import EnergyVadProvider, SileroVadLiteProvider, VadProvider


@dataclass
class AudioStreamConfig:
    format: str = "pcm_s16le"
    sample_rate: int = 16000
    channels: int = 1
    vad_mode: str = "server"  # "client" | "server"


@dataclass
class AudioStreamState:
    active: bool = False
    cfg: AudioStreamConfig | None = None
    vad: VadProvider = field(default_factory=EnergyVadProvider)
    pcm16: bytearray = field(default_factory=bytearray)
    started_at: float = 0.0
    last_chunk_at: float = 0.0

    def start(self, cfg: AudioStreamConfig) -> None:
        self.active = True
        self.cfg = cfg
        self.vad = _make_vad_provider()
        self.vad.reset()
        self.pcm16.clear()
        now = time.monotonic()
        self.started_at = now
        self.last_chunk_at = now

    def stop(self) -> None:
        self.active = False
        self.cfg = None
        self.vad.reset()
        self.pcm16.clear()
        self.started_at = 0.0
        self.last_chunk_at = 0.0


def _make_vad_provider() -> VadProvider:
    if VAD_BACKEND == "silero_vad_lite":
        try:
            return SileroVadLiteProvider()
        except Exception:
            return EnergyVadProvider()
    return EnergyVadProvider()
