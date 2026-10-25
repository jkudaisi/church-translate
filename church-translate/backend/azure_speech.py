"""Shared Azure Speech SDK config for recognition and TTS."""

from __future__ import annotations

import azure.cognitiveservices.speech as speechsdk

from config import AUDIO_LANGUAGES, get_settings


def _speech_kwargs() -> dict[str, str]:
    """Key plus exactly one of region or endpoint.

    The Speech SDK rejects constructing SpeechConfig / SpeechTranslationConfig
    with both. A region wins when both env vars are set: a generic resource
    host such as https://eastus.api.cognitive.microsoft.com/ is not a valid
    speech-translation endpoint, and passing it would override a good region.
    """
    settings = get_settings()
    if not settings.azure_speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY is not set")
    if settings.azure_speech_region:
        return {
            "subscription": settings.azure_speech_key,
            "region": settings.azure_speech_region,
        }
    if settings.azure_speech_endpoint:
        return {
            "subscription": settings.azure_speech_key,
            "endpoint": settings.azure_speech_endpoint,
        }
    raise RuntimeError("AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT is not set")


def build_speech_config() -> speechsdk.SpeechConfig:
    return speechsdk.SpeechConfig(**_speech_kwargs())


def build_translation_config() -> speechsdk.translation.SpeechTranslationConfig:
    settings = get_settings()
    config = speechsdk.translation.SpeechTranslationConfig(**_speech_kwargs())
    config.speech_recognition_language = settings.source_language
    for lang in AUDIO_LANGUAGES:
        config.add_target_language(lang)
    return config
