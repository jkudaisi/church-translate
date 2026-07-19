from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

import speech_capture
from config import ALL_LANGUAGES, AUDIO_LANGUAGES

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
OUTPUT_HTML = FRONTEND_DIR / "output.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    speech_capture.start()
    yield
    speech_capture.stop()


app = FastAPI(title="Church Live Translate", lifespan=lifespan)


@app.get("/")
@app.get("/output.html")
def output_page():
    return FileResponse(OUTPUT_HTML)


@app.get("/health")
def health():
    return {"status": "listening", "languages": list(ALL_LANGUAGES.keys())}


@app.get("/languages")
def languages():
    return {
        "audio_and_captions": list(AUDIO_LANGUAGES.keys()),
        "captions_only": [l for l in ALL_LANGUAGES if l not in AUDIO_LANGUAGES],
    }
