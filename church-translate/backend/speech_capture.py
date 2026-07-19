"""
Core pipeline: captures audio from the laptop's default microphone, runs
continuous English -> {es, fr} speech translation via Azure, then fans out
to TTS (es/fr audio) and Azure Translator (yo/ig captions) per segment.

This runs as a native Python process on the laptop at the venue -- it does
NOT need a browser tab capturing the mic. The Speech SDK talks to the
microphone directly, which is simpler and avoids browser mic-permission /
HTTPS quirks entirely.
"""
import concurrent.futures

import azure.cognitiveservices.speech as speechsdk

from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, SOURCE_LANGUAGE, AUDIO_LANGUAGES, CAPTION_ONLY_LANGUAGES
from translator_client import translate_text
from tts import synthesize
from broadcast import broadcast_caption, broadcast_audio

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)


def _handle_audio_language(lang: str, text: str) -> None:
    """Caption immediately, then synthesize + broadcast audio when ready."""
    broadcast_caption(lang, text)
    audio_bytes = synthesize(lang, text)
    if audio_bytes:
        broadcast_audio(lang, audio_bytes)


def _handle_caption_only_languages(source_text: str) -> None:
    """One Translator call covering both yo and ig, then broadcast each."""
    langs = list(CAPTION_ONLY_LANGUAGES.keys())
    translations = translate_text(source_text, langs)
    for lang, text in translations.items():
        broadcast_caption(lang, text)


def _on_recognized(evt: speechsdk.translation.TranslationRecognitionEventArgs) -> None:
    result = evt.result
    if result.reason != speechsdk.ResultReason.TranslatedSpeech:
        return

    source_text = result.text
    if not source_text.strip():
        return

    # es/fr: text already comes back from the recognizer itself.
    for lang in AUDIO_LANGUAGES:
        translated = result.translations.get(lang)
        if translated:
            _executor.submit(_handle_audio_language, lang, translated)

    # yo/ig: no Azure speech-translation support, so translate the source
    # text separately via the text Translator API.
    _executor.submit(_handle_caption_only_languages, source_text)


def _on_canceled(evt: speechsdk.translation.TranslationRecognitionCanceledEventArgs) -> None:
    print(f"[speech_capture] recognition canceled: {evt.reason} - {evt.error_details}")


def build_recognizer() -> speechsdk.translation.TranslationRecognizer:
    translation_config = speechsdk.translation.SpeechTranslationConfig(
        subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION
    )
    translation_config.speech_recognition_language = SOURCE_LANGUAGE
    for lang in AUDIO_LANGUAGES:
        translation_config.add_target_language(lang)

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=translation_config, audio_config=audio_config
    )

    recognizer.recognized.connect(_on_recognized)
    recognizer.canceled.connect(_on_canceled)

    return recognizer


_recognizer: speechsdk.translation.TranslationRecognizer | None = None


def start() -> None:
    global _recognizer
    if _recognizer is not None:
        return
    _recognizer = build_recognizer()
    _recognizer.start_continuous_recognition()
    print("[speech_capture] listening on default microphone...")


def stop() -> None:
    global _recognizer
    if _recognizer is None:
        return
    _recognizer.stop_continuous_recognition()
    _recognizer = None
    print("[speech_capture] stopped.")
