"""
English speech input.

Microphone and WAV-file modes use Azure Speech Translation for es/fr.
Yoruba and Igbo are filled in by the text Translator inside the pipeline.
Text mode does not open a microphone; POST /ingest (or TEXT_FILE) feeds lines.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

from azure_speech import build_translation_config
from config import assert_never, get_settings
from pipeline import process_english_segment, submit_segment

_recognizer: speechsdk.translation.TranslationRecognizer | None = None
_lock = threading.Lock()


def is_listening() -> bool:
    return _recognizer is not None


def _on_recognized(evt: speechsdk.translation.TranslationRecognitionEventArgs) -> None:
    result = evt.result
    if result.reason == speechsdk.ResultReason.TranslatedSpeech:
        source_text = result.text or ""
        if source_text.strip():
            # Copy now. The SDK can reuse the result after the callback returns.
            submit_segment(source_text, dict(result.translations))
        return
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"[speech_capture] heard English but it was not translated: {result.text}")
        return
    if result.reason == speechsdk.ResultReason.NoMatch:
        return
    print(f"[speech_capture] unrecognized result: {result.reason}")


def _on_canceled(evt: speechsdk.translation.TranslationRecognitionCanceledEventArgs) -> None:
    details = evt.cancellation_details
    print(f"[speech_capture] canceled: {details.reason}")
    if details.reason == speechsdk.CancellationReason.Error:
        print(f"[speech_capture] {details.error_details}")


def _on_session_stopped(_evt: speechsdk.SessionEventArgs) -> None:
    print("[speech_capture] session stopped")


def build_recognizer(*, filename: str | None = None) -> speechsdk.translation.TranslationRecognizer:
    translation_config = build_translation_config()
    if filename:
        audio_config = speechsdk.audio.AudioConfig(filename=filename)
    else:
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=translation_config,
        audio_config=audio_config,
    )
    recognizer.recognized.connect(_on_recognized)
    recognizer.canceled.connect(_on_canceled)
    recognizer.session_stopped.connect(_on_session_stopped)
    return recognizer


def _feed_text_file(path: str) -> None:
    file_path = Path(path)
    if not file_path.is_file():
        print(f"[speech_capture] TEXT_FILE not found: {path}")
        return

    def _run() -> None:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            process_english_segment(stripped)
            time.sleep(0.8)

    threading.Thread(target=_run, name="text-file", daemon=True).start()
    print(f"[speech_capture] feeding lines from {path}")


def start() -> None:
    global _recognizer
    settings = get_settings()
    mode = settings.input_mode
    if mode == "text":
        print("[speech_capture] text input. POST /ingest with an English line.")
        if settings.text_file:
            _feed_text_file(settings.text_file)
        return
    if mode == "file":
        if not settings.audio_file or not Path(settings.audio_file).is_file():
            raise RuntimeError(f"AUDIO_FILE not found: {settings.audio_file or '(empty)'}")
        filename = settings.audio_file
    elif mode == "microphone":
        filename = None
    else:
        assert_never(mode)
        return

    with _lock:
        if _recognizer is not None:
            return
        _recognizer = build_recognizer(filename=filename)
        # Synchronous start, matching the Speech translation how-to.
        _recognizer.start_continuous_recognition()
    if filename:
        print(f"[speech_capture] reading {filename}")
    else:
        print("[speech_capture] listening on the default microphone")


def stop() -> None:
    global _recognizer
    with _lock:
        recognizer = _recognizer
        _recognizer = None
    if recognizer is None:
        return
    recognizer.stop_continuous_recognition()
    print("[speech_capture] stopped")
