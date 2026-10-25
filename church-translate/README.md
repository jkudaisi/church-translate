# Church Live Translate

English from a laptop microphone becomes live captions in Spanish, French,
Yoruba, and Igbo. Spanish and French also get spoken audio. Phones open one
static page, pick a language, and listen over Supabase Realtime.

Yoruba and Igbo are captions only. Azure Speech has no speech-translation
or neural voice for either language. Azure Translator's text API does.

## Run it on Sunday

Do the laptop sound check (step 4) before you create any cloud accounts.
That path needs no keys and no microphone.

### 1. Azure

Create two resources in the same region if you can (for example `eastus`):

1. **Speech** (Azure AI Speech). This one resource does English speech
   translation into Spanish and French, and the Spanish/French voices.
   Copy **Key 1** and the **region**.
2. **Translator** (Azure AI Translator). This is a separate resource.
   Copy **Key 1**, the **region**, and the **endpoint**.
   - Global endpoint: `https://api.cognitive.microsofttranslator.com`
   - Resource endpoint: `https://<name>.cognitiveservices.azure.com`
   Paste whichever the portal shows. The app adds the right path.

Speech translation targets are the language codes `es` and `fr`.
Translator targets for the caption-only languages are `yo` and `ig`.

### 2. Supabase

1. Create a project.
2. In **Project Settings → API keys**, copy:
   - Project URL
   - The **anon** public key, or the newer **publishable** key (`sb_publishable_...`). This one goes in the browser.
   - The **service_role** key, or the newer **secret** key (`sb_secret_...`). This one stays on the laptop. Do not put it in `config.js` or in the HTML.
3. Leave Realtime Broadcast on (it is on by default).
4. The app uses a **public** channel. Do not mark the channel private, and do not require a logged-in user. No database table and no RLS policy is required for this broadcast.
5. On the free plan a broadcast larger than 256 KB is dropped. Spoken lines are sent as 16 kHz, 32 kbps mono MP3 so a normal sentence fits. Leave **Realtime → Settings → Max payload size** at the plan default.

### 3. Fill in the laptop env file

```bash
cd church-translate/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

| Variable | Value |
| --- | --- |
| `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` | Speech resource |
| `AZURE_TRANSLATOR_KEY` / `AZURE_TRANSLATOR_REGION` / `AZURE_TRANSLATOR_ENDPOINT` | Translator resource |
| `SUPABASE_URL` | Project URL |
| `SUPABASE_SERVICE_KEY` | service_role or `sb_secret_` key |
| `SUPABASE_ANON_KEY` | anon or `sb_publishable_` key |
| `RUN_MODE` | `live` |

Leave `RUN_MODE` blank until the keys are real. Placeholder values from
`.env.example` stay in demo mode on purpose.

`AZURE_SPEECH_ENDPOINT` is optional. When both it and `AZURE_SPEECH_REGION`
are set, the Speech SDK is built from the region. The endpoint is used only
when the region is empty. Leave the endpoint blank if the portal copied a
generic host such as `https://eastus.api.cognitive.microsoft.com/`; that
URL is not a valid speech-translation endpoint.

Voices default to `es-ES-ElviraNeural` and `fr-FR-DeniseNeural`. Change the
names in `backend/config.py` if you want another locale (for example an
`es-MX` voice). Both names are in the current Azure voice list.

### 4. Sound check on the laptop (no mic, no cloud)

From `church-translate/backend`, with the virtualenv active:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. You should see a demo banner.

1. Tap **Español**.
2. Type `Good morning, church. Let us pray.` and press **Send test line**.
3. The caption should read `[es] Good morning, church. Let us pray.` and a short tone should play. Use **Audio: On** if the browser blocked sound; the first tap on a language button is what unlocks audio.
4. Tap **Yorùbá**. Send another line. You get a caption and no audio button. French and Igbo work the same way.

Or from another terminal:

```bash
curl -s -X POST http://127.0.0.1:8000/ingest \
  -H 'content-type: application/json' \
  -d '{"text":"Good morning, church. Let us pray."}'
```

A caption that starts with `[es]` means mock translation. The tone is not a voice.
Quit with Ctrl-C when you are done.

### 5. Start the live service

Put the real keys in `.env`, set `RUN_MODE=live`, and start the same command.
The terminal should say `run mode: live`, `input: microphone`,
`translation: azure`, `broadcast: supabase`, then
`listening on the default microphone`.

Speak a sentence. On the laptop open <http://127.0.0.1:8000/>, tap **Español**,
and confirm a real Spanish caption and a voice (not the demo tone). The page
is now subscribed to Supabase, same as a phone.

The mic is whatever the operating system calls the default input. A lapel or
handheld mic close to the speaker matters more than any setting here.
On Linux the Speech SDK needs a working microphone device (`libasound`).

To rehearse from a WAV instead of the mic, set `INPUT_MODE=file` and
`AUDIO_FILE` to a PCM WAV (16 kHz, 16-bit, mono is the safest). The file
plays through once and then recognition stops.

### 6. Host the phone page

`frontend/output.html` is a static file. Host it anywhere the phones can
open (GitHub Pages, Supabase Storage, or any web server).

1. Copy `frontend/config.example.js` to `frontend/config.js` in the **same folder** as `output.html`.
2. Set `supabaseUrl` and `supabaseAnonKey` (anon or publishable key only).
3. Upload both files together. The page loads `config.js` next to itself.
4. Open the URL on a phone, tap a language, and speak on the laptop.

Share that URL or a QR code. The phone never sees the Azure keys or the
Supabase service key.

Keep the backend on the laptop that has the microphone. Phones do not
connect to the laptop; they connect to Supabase. `127.0.0.1` is enough.
Use `--host 0.0.0.0` only if something else on the local network must open
the laptop page. `/ingest` is open on whatever interface you bind.

### 7. In the room

1. Start the backend and leave the terminal visible.
2. Confirm one phone shows Spanish captions and audio, and another shows Yoruba captions.
3. If a caption never arrives, check the terminal for `[broadcast] supabase HTTP ...`. A 422 means the audio clip was over the payload limit. A 401 means the service key is wrong.
4. If the phone says it could not join the channel, the anon key is wrong, or the project is blocking public Realtime channels.
5. To see captions from this laptop even when Supabase is the problem, open <http://127.0.0.1:8000/?transport=local>. Typed lines still work in live mode: `POST /ingest` with `{"text":"..."}` runs them through Azure Translator and TTS without the microphone.

Captions usually land within a couple of seconds. Audio follows after the
voice is synthesized. Expect a short gap between sentences; MP3 clips are
played back to back, not mixed into one stream.

## What the code does

- `speech_capture.py` reads the default microphone, or a WAV file, with the Speech SDK. Continuous recognition translates English into `es` and `fr`.
- `pipeline.py` sends Yoruba and Igbo (and Spanish/French, when the line was typed rather than spoken) through Translator.
- `tts.py` synthesizes `es` and `fr` to mono MP3.
- `broadcast.py` POSTs each caption and audio clip to Supabase Realtime. The Python sync client cannot do this: in supabase-py 2.33, `create_client().channel()` raises `NotImplementedError`, and `send_broadcast` is an async WebSocket call. The REST broadcast API is the supported server-side send.
- `frontend/output.html` subscribes to `church-translate:es` (and `fr`, `yo`, `ig`) as a public channel. It decodes the audio with the Web Audio API and falls back to an audio element.

Demo mode (`RUN_MODE=demo`, the default with no keys) skips Azure and Supabase. Typed lines are marked `[es]`, `[fr]`, `[yo]`, `[ig]`, and Spanish/French play a WAV tone through the same player.

## Tests

```bash
cd church-translate/backend
pip install -r requirements-dev.txt
pytest
```

## Notes

- Background noise in the room will hurt accuracy more than the code will.
- TTS and Translator run for every recognized line, even if nobody is listening in that language.
- Azure Speech does not bill you in demo mode. Live mode does, for speech translation, Translator text, and TTS.
- On Linux the Speech SDK may segfault when synthesizing directly to a WAV file (`AudioOutputConfig` with a filename). Helpers that make test WAVs should call the TTS REST API or synthesize in memory (`audio_config=None`) and write the bytes themselves. This app's live voices stay in memory as MP3, and the demo tone is written with Python's `wave` module, not the SDK.
