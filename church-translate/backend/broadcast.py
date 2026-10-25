"""
Fan-out for captions and audio.

supabase-py 2.33's sync client raises NotImplementedError from channel().
Realtime on that release only exists on the async client, and
AsyncRealtimeChannel.send_broadcast is a coroutine that pushes over a
WebSocket after subscribe() reaches SUBSCRIBED. Speech SDK callbacks are
synchronous threads, so the scaffold's send_broadcast call cannot work.

Server-side sends use the Realtime REST broadcast endpoint instead, which
is the documented way to publish without holding a socket:

    POST {SUPABASE_URL}/realtime/v1/api/broadcast/{topic}/events/{event}
    apikey + Authorization: Bearer <service key>
    body: the JSON payload itself (not wrapped)

The topic is the bare channel name (`church-translate:es`). supabase-js
subscribes to `realtime:church-translate:es` on the socket and strips that
prefix when it calls this same REST endpoint. Adding `realtime:` here
drops the message.

The browser channel is public (`private: false`, the JS default). This
request omits `?private=true` so the two sides match. A public message does
not reach a private channel.

Demo mode (and every live send) also mirrors onto an in-process hub so the
page served by this laptop can render captions with no Supabase project.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from collections import defaultdict
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import requests

from config import ALL_LANGUAGES, assert_never, get_settings

CHANNEL_PREFIX = "church-translate"
# Free-plan ceiling. Pro is much higher. Oversized REST broadcasts return 422.
# https://supabase.com/docs/guides/realtime/limits
FREE_PLAN_PAYLOAD_BYTES = 256 * 1024
_WARN_PAYLOAD_BYTES = 240 * 1024


def channel_name(lang: str) -> str:
    return f"{CHANNEL_PREFIX}:{lang}"


def build_broadcast_url(supabase_url: str, topic: str, event: str, *, private: bool = False) -> str:
    parts = urlsplit(supabase_url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"SUPABASE_URL is not a URL: {supabase_url}")
    path = "/realtime/v1/api/broadcast/{topic}/events/{event}".format(
        topic=quote(topic, safe=""),
        event=quote(event, safe=""),
    )
    query = "private=true" if private else ""
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


class LocalHub:
    """In-process pub/sub used by the laptop page and by tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self.events: list[tuple[str, str, dict[str, Any]]] = []
        self.last_caption: dict[str, dict[str, Any]] = {}

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def reset(self) -> None:
        with self._lock:
            self.events.clear()
            self.last_caption.clear()
            self._subs.clear()
            self._loop = None

    def publish(self, lang: str, event: str, payload: dict[str, Any]) -> None:
        message = {"event": event, "payload": payload}
        with self._lock:
            self.events.append((lang, event, payload))
            if event == "caption":
                self.last_caption[lang] = dict(payload)
            loop = self._loop
            subscribers = list(self._subs.get(lang, ()))
        if loop is None or loop.is_closed() or not loop.is_running() or not subscribers:
            return
        loop.call_soon_threadsafe(self._fanout, lang, message)

    def _fanout(self, lang: str, message: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subs.get(lang, ()))
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    def subscribe(self, lang: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=32)
        with self._lock:
            self._subs[lang].add(queue)
        return queue

    def unsubscribe(self, lang: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subs[lang].discard(queue)

    def caption_snapshot(self, lang: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self.last_caption.get(lang)
            return dict(payload) if payload else None


local_hub = LocalHub()


def broadcast_caption(lang: str, text: str) -> None:
    if lang not in ALL_LANGUAGES or not text.strip():
        return
    _send(lang, "caption", {"text": text, "ts": time.time()})


def broadcast_audio(lang: str, audio_bytes: bytes, content_type: str) -> None:
    if lang not in ALL_LANGUAGES or not audio_bytes:
        return
    payload = {
        "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
        "content_type": content_type,
        "ts": time.time(),
    }
    encoded = json.dumps(payload)
    if len(encoded.encode("utf-8")) > _WARN_PAYLOAD_BYTES:
        print(
            f"[broadcast] {lang} audio payload is {len(encoded)} bytes. "
            f"Supabase free-plan broadcasts over {FREE_PLAN_PAYLOAD_BYTES} bytes are dropped."
        )
    _send(lang, "audio", payload)


def _send(lang: str, event: str, payload: dict[str, Any]) -> None:
    # Always mirror locally so the laptop page and /latest stay in sync
    # even when the phone page is on Supabase.
    local_hub.publish(lang, event, payload)

    settings = get_settings()
    mode = settings.broadcast_mode
    if mode == "local":
        return
    if mode == "supabase":
        _supabase_rest(lang, event, payload)
        return
    assert_never(mode)


def _supabase_rest(lang: str, event: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        print("[broadcast] skipping Supabase send; URL or service key is missing")
        return

    url = build_broadcast_url(settings.supabase_url, channel_name(lang), event, private=False)
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8")
    try:
        response = requests.post(url, headers=headers, data=body, timeout=5)
    except requests.RequestException as exc:
        print(f"[broadcast] supabase request failed for {lang}/{event}: {exc}")
        return
    if response.status_code not in {200, 202}:
        detail = response.text[:300].replace("\n", " ")
        print(f"[broadcast] supabase HTTP {response.status_code} for {lang}/{event}: {detail}")
