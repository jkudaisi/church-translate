"""
Fan-out layer: pushes captions/audio to Supabase Realtime, one channel per
language, so the output pages (opened via link/QR code) just subscribe to
the channel for whichever language the person picks.
"""
import base64
import time

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, ALL_LANGUAGES

_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
_channels: dict[str, object] = {}


def _channel(lang: str):
    """Lazily create + subscribe a broadcast channel per language, then cache it."""
    if lang not in _channels:
        ch = _client.channel(f"church-translate:{lang}")
        ch.subscribe()
        _channels[lang] = ch
    return _channels[lang]


def broadcast_caption(lang: str, text: str) -> None:
    if lang not in ALL_LANGUAGES:
        return
    _channel(lang).send_broadcast(
        "caption",
        {"text": text, "ts": time.time()},
    )


def broadcast_audio(lang: str, audio_bytes: bytes) -> None:
    if lang not in ALL_LANGUAGES:
        return
    _channel(lang).send_broadcast(
        "audio",
        {"audio_b64": base64.b64encode(audio_bytes).decode("ascii"), "ts": time.time()},
    )
