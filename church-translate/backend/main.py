"""Laptop service: capture or ingest English, fan out captions and audio."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

import speech_capture
from broadcast import local_hub
from config import ALL_LANGUAGES, AUDIO_LANGUAGES, configuration_errors, get_settings, load_settings
from pipeline import process_english_segment

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
OUTPUT_HTML = FRONTEND_DIR / "output.html"
_NO_STORE = {"Cache-Control": "no-store"}


class IngestBody(BaseModel):
    text: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    local_hub.bind(asyncio.get_running_loop())
    _log_banner()
    errors = configuration_errors(settings)
    if errors:
        detail = "\n".join(f"  - {item}" for item in errors)
        raise RuntimeError("Live mode is not configured:\n" + detail)
    speech_capture.start()
    yield
    speech_capture.stop()


app = FastAPI(title="Church Live Translate", lifespan=lifespan)


def _log_banner() -> None:
    current = get_settings()
    print("Church Live Translate")
    print(f"  run mode:    {current.run_mode}")
    print(f"  input:       {current.input_mode}")
    print(f"  translation: {current.translation_mode}")
    print(f"  broadcast:   {current.broadcast_mode}")
    for warning in current.warnings:
        print(f"  warning:     {warning}")


@app.get("/")
@app.get("/output.html")
def output_page() -> FileResponse:
    if not OUTPUT_HTML.is_file():
        raise HTTPException(status_code=404, detail="output.html is missing")
    return FileResponse(OUTPUT_HTML, headers=_NO_STORE)


@app.get("/config.js")
def config_js() -> Response:
    """Public browser settings. This response never includes the service key."""
    payload = get_settings().browser_config()
    body = "window.CHURCH_TRANSLATE_CONFIG = " + json.dumps(payload) + ";\n"
    return Response(content=body, media_type="application/javascript", headers=_NO_STORE)


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    if settings.run_mode == "demo":
        status = "demo"
    elif speech_capture.is_listening():
        status = "listening"
    elif settings.input_mode == "text":
        status = "ready"
    else:
        status = "idle"
    return {
        "status": status,
        "run_mode": settings.run_mode,
        "input_mode": settings.input_mode,
        "translation_mode": settings.translation_mode,
        "broadcast_mode": settings.broadcast_mode,
        "languages": list(ALL_LANGUAGES),
    }


@app.get("/languages")
def languages() -> dict[str, list[str]]:
    return {
        "audio_and_captions": list(AUDIO_LANGUAGES),
        "captions_only": [lang for lang in ALL_LANGUAGES if lang not in AUDIO_LANGUAGES],
    }


@app.post("/ingest")
async def ingest(body: IngestBody) -> dict[str, object]:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return await asyncio.to_thread(process_english_segment, text)


@app.get("/latest/{lang}")
def latest(lang: str) -> dict[str, object]:
    if lang not in ALL_LANGUAGES:
        raise HTTPException(status_code=404, detail="unknown language")
    return {"lang": lang, "caption": local_hub.caption_snapshot(lang)}


@app.websocket("/ws/{lang}")
async def captions_socket(websocket: WebSocket, lang: str) -> None:
    if lang not in ALL_LANGUAGES:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = local_hub.subscribe(lang)
    try:
        snapshot = local_hub.caption_snapshot(lang)
        if snapshot is not None:
            await websocket.send_json({"event": "caption", "payload": snapshot})
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        return
    finally:
        local_hub.unsubscribe(lang, queue)
