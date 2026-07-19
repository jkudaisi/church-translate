"""
Text-to-speech for the audio-capable languages (Spanish, French).
Runs as a plain TTS call on already-translated text, decoupled from the
TranslationRecognizer, so it can happen in parallel per language and never
blocks recognition.
"""
import azure.cognitiveservices.speech as speechsdk

from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, AUDIO_LANGUAGES

# Keep one SpeechConfig per voice; synthesizer objects are cheap to create per call.
_output_format = speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3


def synthesize(lang: str, text: str) -> bytes | None:
    """
    Synthesize `text` (already translated) into speech for `lang`.
    Returns raw MP3 bytes, or None on failure.
    """
    voice_name = AUDIO_LANGUAGES.get(lang)
    if not voice_name or not text.strip():
        return None

    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION
    )
    speech_config.speech_synthesis_voice_name = voice_name
    speech_config.set_speech_synthesis_output_format(_output_format)

    # audio_config=None => audio is returned in-memory instead of played on a speaker
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        print(f"[tts] synthesis canceled for '{lang}': {details.reason} - {details.error_details}")
    return None
