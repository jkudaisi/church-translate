"""Shared Azure Speech SDK config for recognition and TTS."""

from __future__ import annotations

import azure.cognitiveservices.speech as speechsdk

from config import AUDIO_LANGUAGES, get_settings


def _speech_kwargs() -> dict[str, str]:
    settings = get_settings()
    if not settings.azure_speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY is not set")
    if settings.azure_speech_endpoint:
        return {
            "subscription": settings.azure_speech_key,
            "endpoint": settings.azure_speech_endpoint,
        }
    if not settings.azure_speech_region:
        raise RuntimeError("AZURE_SPEECH_REGION is not set")
    return {
        "subscription": settings.azure_speech_key,
        "region": settings.azure_speech_region,
    }


def build_speech_config() -> speechsdk.SpeechConfig:
    return speechsdk.SpeechConfig(**_speech_kwargs())


def build_translation_config() -> speechsdk.translation.SpeechTranslationConfig:
    settings = get_settings()
    config = speechsdk.translation.SpeechTranslationConfig(**_speech_kwargs())
    config.speech_recognition_language = settings.source_language
    for lang in AUDIO_LANGUAGES:
        config.add_target_language(lang)
    return config
