# Church Live Translate — scaffold

English mic input on a laptop -> live translated captions (Spanish, French,
Yoruba, Igbo) + live translated audio (Spanish, French only — Azure has no
speech-to-text/TTS support for Yoruba or Igbo).

## How it works

- `backend/speech_capture.py` runs on the laptop and captures the **default
  microphone directly through the Python Speech SDK** — no browser tab or
  mic permissions needed for the capture side. It runs continuous English ->
  {es, fr} translation.
- For `yo`/`ig`, each recognized English segment gets a second pass through
  Azure's **Translator** (text) API, since neither language exists in
  Azure's speech-to-text/speech-translation locale list.
- For `es`/`fr`, translated text is sent to Azure TTS in parallel and the
  resulting audio is broadcast alongside the caption.
- Everything fans out over **Supabase Realtime**, one channel per language:
  `church-translate:es`, `church-translate:fr`, `church-translate:yo`,
  `church-translate:ig`.
- `frontend/output.html` is a static page: pick a language, get captions
  (and audio, for es/fr). Host it anywhere (Supabase Storage, GitHub Pages,
  Vercel) and share the link/QR code — it only needs the Supabase anon key,
  never your Azure or Supabase service keys.

## Setup

1. `cd backend && pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in:
   - Azure **Speech** resource key/region (Spanish/French pipeline + TTS)
   - Azure **Translator** resource key/region (Yoruba/Igbo captions —
     this is a separate Azure resource from Speech)
   - Supabase project URL + **service role key** (backend only — never
     ship the service key to the browser)
3. In `frontend/output.html`, set `SUPABASE_URL` and `SUPABASE_ANON_KEY`
   (the public anon key, not the service key).
4. Run the backend on the laptop that'll sit near the mic:
   ```
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
5. Host `output.html` and share the link / a QR code pointing to it.

## Things to verify before the actual service

- **Supabase broadcast API**: `broadcast.py` uses `channel.send_broadcast(event, payload)`.
  Double-check this method name against the currently installed `supabase-py`
  version's docs before relying on it — the realtime client's API has moved
  around across versions.
- **Mic quality**: a lapel/handheld mic close to the speaker will matter far
  more than any setting in this code. Background noise in a sanctuary is
  the single biggest accuracy risk.
- **Voices**: `config.py` uses `es-ES-ElviraNeural` and `fr-FR-DeniseNeural`
  as placeholders — browse the Azure Voice Gallery and swap in whichever
  voices/locales (e.g. `es-MX` vs `es-ES`) match your congregation.
- **Cost control**: right now TTS and Translator calls fire on every
  recognized segment regardless of whether anyone's listening in that
  language. Once this is working, a reasonable next step is tracking active
  subscriber counts per Supabase channel and skipping the TTS/translation
  call for languages with zero listeners.
- **Latency**: expect captions within ~1-2s of speech, audio a beat behind
  that (TTS synthesis time). Fine for captions; test in the room before
  trusting it for a fully "dubbed" experience.
