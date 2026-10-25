"""Lock the SDK surfaces this app was checked against."""

from __future__ import annotations

import inspect

import azure.cognitiveservices.speech as speechsdk
import pytest


def test_speech_sdk_methods_we_call() -> None:
    recognizer = speechsdk.translation.TranslationRecognizer
    assert callable(recognizer.start_continuous_recognition)
    assert callable(recognizer.stop_continuous_recognition)
    canceled = speechsdk.translation.TranslationRecognitionCanceledEventArgs
    assert "cancellation_details" in canceled.__dict__ or hasattr(canceled, "cancellation_details")
    audio_signature = inspect.signature(speechsdk.audio.AudioConfig.__init__)
    assert "filename" in audio_signature.parameters
    assert "use_default_microphone" in audio_signature.parameters
    assert hasattr(speechsdk.SpeechSynthesisOutputFormat, "Audio16Khz32KBitRateMonoMp3")
    synth_signature = inspect.signature(speechsdk.SpeechSynthesizer.__init__)
    assert "audio_config" in synth_signature.parameters


def test_file_audio_config_accepts_wav(tmp_path) -> None:
    from tts import tone_wav

    wav_path = tmp_path / "line.wav"
    wav_path.write_bytes(tone_wav("hello"))
    config = speechsdk.audio.AudioConfig(filename=str(wav_path))
    assert config is not None


def test_sync_supabase_client_cannot_broadcast() -> None:
    """supabase-py 2.33: realtime exists only on the async client."""
    from supabase import create_client

    client = create_client("https://example.supabase.co", "public-anon-key")
    with pytest.raises(NotImplementedError, match="async client"):
        client.channel("church-translate:es")


def test_async_send_broadcast_is_a_coroutine() -> None:
    from realtime._async.channel import AsyncRealtimeChannel

    assert inspect.iscoroutinefunction(AsyncRealtimeChannel.send_broadcast)
