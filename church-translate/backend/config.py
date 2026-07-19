import os
from dotenv import load_dotenv

load_dotenv()

AZURE_SPEECH_KEY = os.environ["AZURE_SPEECH_KEY"]
AZURE_SPEECH_REGION = os.environ["AZURE_SPEECH_REGION"]

AZURE_TRANSLATOR_KEY = os.environ["AZURE_TRANSLATOR_KEY"]
AZURE_TRANSLATOR_REGION = os.environ["AZURE_TRANSLATOR_REGION"]
AZURE_TRANSLATOR_ENDPOINT = os.environ.get(
    "AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com"
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

SOURCE_LANGUAGE = os.environ.get("SOURCE_LANGUAGE", "en-US")

# Languages handled directly by the Azure TranslationRecognizer (speech->text->speech).
# These get both captions and synthesized audio.
AUDIO_LANGUAGES = {
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
}

# Languages with no Azure speech-translation / TTS support.
# Captions only, produced via a second call to Azure Translator (text API).
CAPTION_ONLY_LANGUAGES = {
    "yo": "Yoruba",
    "ig": "Igbo",
}

ALL_LANGUAGES = {**{k: k for k in AUDIO_LANGUAGES}, **CAPTION_ONLY_LANGUAGES}
