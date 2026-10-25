"""Lock the SDK surfaces this app was checked against."""

from __future__ import annotations

import inspect

import azure.cognitiveservices.speech as speechsdk
import pytest

from azure_speech import build_speech_config, build_translation_config
from config import load_settings


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


def test_speech_config_prefers_region_over_generic_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SPEECH_KEY", "speech-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "https://eastus.api.cognitive.microsoft.com/")
    load_settings()

    endpoint_prop = speechsdk.PropertyId.SpeechServiceConnection_Endpoint
    for config in (build_speech_config(), build_translation_config()):
        assert config.region == "eastus"
        assert config.get_property(endpoint_prop) == ""


def test_speech_config_falls_back_to_endpoint_without_region(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = "https://eastus.stt.speech.microsoft.com"
    monkeypatch.setenv("AZURE_SPEECH_KEY", "speech-key")
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", endpoint)
    load_settings()

    endpoint_prop = speechsdk.PropertyId.SpeechServiceConnection_Endpoint
    for config in (build_speech_config(), build_translation_config()):
        assert config.region == ""
        assert config.get_property(endpoint_prop) == endpoint


def test_speech_config_uses_region_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SPEECH_KEY", "speech-key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
    load_settings()

    endpoint_prop = speechsdk.PropertyId.SpeechServiceConnection_Endpoint
    for config in (build_speech_config(), build_translation_config()):
        assert config.region == "eastus"
        assert config.get_property(endpoint_prop) == ""


def test_speech_config_requires_region_or_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SPEECH_KEY", "speech-key")
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
    load_settings()

    with pytest.raises(RuntimeError, match="AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT"):
        build_speech_config()


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
