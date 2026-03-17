from __future__ import annotations

import asyncio
import io
import math
import wave

from .config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, TTS_PITCH, TTS_RATE, TTS_VOICE, USE_MOCK_SERVICES


async def synthesize(text: str) -> bytes:
    if USE_MOCK_SERVICES or not (AZURE_SPEECH_KEY and AZURE_SPEECH_REGION):
        return _beep_wav(duration_ms=max(120, min(900, 80 * max(1, len(text) // 10))))

    return await asyncio.to_thread(_synthesize_azure_wav, text)


def _synthesize_azure_wav(text: str) -> bytes:
    import azure.cognitiveservices.speech as speechsdk  # type: ignore

    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_synthesis_voice_name = TTS_VOICE
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
    )

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    ssml = f"""
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="my-MM">
  <voice name="{_xml_escape(TTS_VOICE)}">
    <prosody rate="{_xml_escape(TTS_RATE)}" pitch="{_xml_escape(TTS_PITCH)}">{_xml_escape(text)}</prosody>
  </voice>
</speak>
""".strip()

    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return bytes(result.audio_data)

    details = speechsdk.SpeechSynthesisCancellationDetails.from_result(result)
    raise RuntimeError(f"Azure TTS canceled: {details.reason} {details.error_details}")


def _beep_wav(duration_ms: int, freq_hz: int = 660, sample_rate: int = 22050) -> bytes:
    frames = int(sample_rate * (duration_ms / 1000))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(frames):
            t = i / sample_rate
            amp = 0.15
            value = int(amp * 32767 * math.sin(2 * math.pi * freq_hz * t))
            wf.writeframesraw(value.to_bytes(2, "little", signed=True))
    return buf.getvalue()


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
