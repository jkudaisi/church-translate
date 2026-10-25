"""
Text-to-speech for Spanish and French.

Live mode asks Azure Speech for mono 16 kHz, 32 kbps MP3. A spoken line is
small enough for Supabase Realtime's free-plan 256 KB broadcast limit, and
browsers can decode audio/mpeg with decodeAudioData or an <audio> element.

Demo mode writes a short PCM WAV tone. The output page decodes that with the
same player, so the sound check does not need Azure.
"""

from __future__ import annotations

import io
import math
import struct
import wave

import azure.cognitiveservices.speech as speechsdk

from azure_speech import build_speech_config
from config import AUDIO_LANGUAGES, assert_never, get_settings

MP3_CONTENT_TYPE = "audio/mpeg"
WAV_CONTENT_TYPE = "audio/wav"

_TONE_HZ = {"es": 440, "fr": 554}
_OUTPUT_FORMAT = speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3


def tone_wav(text: str, *, frequency_hz: int = 440) -> bytes:
    """A short faded tone whose length grows a little with the line."""
    duration = min(1.2, max(0.35, len(text.strip()) * 0.02))
    sample_rate = 16000
    frame_count = int(sample_rate * duration)
    fade = max(1, int(sample_rate * 0.02))
    frames = bytearray()
    for index in range(frame_count):
        envelope = 1.0
        if index < fade:
            envelope = index / fade
        elif index > frame_count - fade:
            envelope = max(0.0, (frame_count - index) / fade)
        sample = int(
            0.25
            * envelope
            * 32767
            * math.sin(2 * math.pi * frequency_hz * index / sample_rate)
        )
        frames += struct.pack("<h", sample)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return buffer.getvalue()


def synthesize(lang: str, text: str) -> tuple[bytes, str] | None:
    """Return (audio_bytes, content_type), or None when there is nothing to play."""
    if lang not in AUDIO_LANGUAGES or not text.strip():
        return None

    settings = get_settings()
    mode = settings.translation_mode
    if mode == "mock":
        return tone_wav(text, frequency_hz=_TONE_HZ.get(lang, 440)), WAV_CONTENT_TYPE
    if mode == "azure":
        return _azure_synthesize(lang, text)
    assert_never(mode)


def _azure_synthesize(lang: str, text: str) -> tuple[bytes, str] | None:
    voice_name = AUDIO_LANGUAGES[lang]
    try:
        speech_config = build_speech_config()
    except RuntimeError as exc:
        print(f"[tts] {exc}")
        return None

    speech_config.speech_synthesis_voice_name = voice_name
    speech_config.set_speech_synthesis_output_format(_OUTPUT_FORMAT)
    # audio_config=None keeps the bytes on the result instead of the speakers.
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted and result.audio_data:
        return bytes(result.audio_data), MP3_CONTENT_TYPE
    if result.reason == speechsdk.ResultReason.Canceled and result.cancellation_details is not None:
        details = result.cancellation_details
        print(f"[tts] synthesis canceled for {lang}: {details.reason} - {details.error_details}")
    else:
        print(f"[tts] synthesis failed for {lang}: {result.reason}")
    return None
