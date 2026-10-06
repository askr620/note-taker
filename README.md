# MeetNotes

A free, local-first meeting note taker for a Windows PC. React + Vite + Tailwind, FastAPI, SQLite FTS5, WASAPI loopback, faster-whisper, and Ollama. No accounts, subscriptions, Google credentials, telemetry, or paid APIs.

**Start meeting → record locally → transcribe with Whisper → generate notes with Ollama → save locally.**

## Requirements

- Windows 10/11, 64-bit, with an enabled speaker/headphone device.
- Python 3.11–3.13, 64-bit. Python 3.13 was used for development verification.
- Node.js 22.12+ or 24 LTS and npm.
- [Ollama for Windows](https://ollama.com/download/windows), with a downloaded local model.
- Internet for initial dependency/model downloads only. No meeting data is included in these downloads.
- Start with Whisper `base` and `llama3.2:3b`; use `tiny` and `llama3.2:1b` on a lower-memory PC. Actual speed depends on hardware, audio length, and model size. Whisper defaults to CPU/int8; no CUDA setup is required.

## 1. Install the backend

Open PowerShell in the project folder:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe download_model.py base
```

The explicit download command gets the faster-whisper model from Hugging Face into `backend/models/base`. Recording/processing never downloads models automatically. You may also download `tiny`, `small`, or `medium`, then select it in Settings.

You can activate the virtual environment with `.\.venv\Scripts\Activate.ps1` and use `pip install -r requirements.txt` and `python run.py` as usual. If PowerShell blocks activation, use the full `.venv` Python path; changing execution policy is unnecessary.

## 2. Install and configure Ollama

Install Ollama from the official Windows download above. Then open a new PowerShell window:

```powershell
# Keep Ollama local-only. Persist this for your Windows user, then quit/restart Ollama.
[Environment]::SetEnvironmentVariable('OLLAMA_NO_CLOUD', '1', 'User')
$env:OLLAMA_NO_CLOUD = '1'
ollama pull llama3.2:3b
ollama list
```

Ollama normally runs as a tray application. If it is not running, start the application or use `ollama serve` in a separate terminal. Do not start a second server if the tray app already owns port 11434.

For a smaller model, run `ollama pull llama3.2:1b`, then choose it in MeetNotes Settings. The dropdown lists installed local models. MeetNotes will not pull a model during a meeting.

Ollama must listen on loopback at `http://127.0.0.1:11434`. MeetNotes rejects external Ollama URLs, does not follow HTTP redirects or environment proxy settings, and rejects cloud/remote models using the model name and metadata. Set `OLLAMA_NO_CLOUD=1` in Ollama itself as defense in depth. See the [official Ollama local-only instructions](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).

## 3. Run the backend

```powershell
cd backend
.\.venv\Scripts\python.exe run.py
```

The API starts at [127.0.0.1:8000](http://127.0.0.1:8000). The database and data directories initialize automatically. API docs: [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Run **one backend process**, without `--reload` or extra workers. An OS file lock prevents two instances from using the same data directory. Keep the terminal open during recording and processing.

## 4. Run the frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [127.0.0.1:5173](http://127.0.0.1:5173). The Vite server proxies `/api` to the local backend. If PowerShell blocks `npm.ps1`, use `npm.cmd` instead of `npm`.

### One-server everyday use

```powershell
cd frontend
npm run build
cd ../backend
.\.venv\Scripts\python.exe run.py
```

Build **before starting/restarting the backend**. FastAPI then serves `frontend/dist` at [127.0.0.1:8000](http://127.0.0.1:8000); no separate Vite server is needed. Hash routing supports refreshes on meeting/settings pages. `npm run preview` does not proxy API calls: use Vite development mode or this one-server mode.

## Windows audio setup

### Hindi speech → English text

In **Settings**, set **Transcript output → Translate to English** (the default), choose **Spoken language → Hindi** or **Detect automatically**, and save. New recordings and transcription retries use Whisper's local `translate` task and produce timestamped English text. AI note generation is instructed to write English notes. The Transcript tab labels translated output and retains the detected source language as metadata. This is text translation, not English audio dubbing.

Choose **Keep original language** to retain Hindi text instead. Existing transcripts are not automatically rewritten. Translation can mishear names, dates, or mixed-language speech, so review the saved recording. The multilingual base model already supports this mode; no additional translation service or download is required.

1. Open Google Meet yourself and join normally. MeetNotes does not log into or control Meet.
2. In Meet’s audio settings, note the selected **speaker/output** device.
3. In MeetNotes, click **Start Meeting**, enter a title, and select the matching **System audio — … [Loopback]** device.
4. Obtain any consent required to record/transcribe and check the consent box. Click **Start Meeting**.
5. Use **Pause**, **Resume**, and **Stop Meeting**. A visible recording indicator and recorded-audio timer show the state. After stopping, processing starts automatically.
6. Review the transcript and AI notes. Edit notes or action items and export as Markdown, TXT, Word, or PDF.

**System audio captures the selected output, including other apps’ notifications/music. It generally does not include your own microphone.** This MVP records one source at a time: system audio OR a microphone. Microphone selection records that input only; it does not magically capture the other participants. There is no speaker identification or simultaneous mic/system mixing. Use a deliberately configured Windows recording/mix device if you already have one; future sources can implement the `Recorder` protocol.

Choose the correct device each time, particularly after connecting headphones or switching Bluetooth profiles. Do not change the output device during a recording. WASAPI loopback is provided by [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch); no browser screen sharing or paid recording API is required.

Pauses discard incoming frames. Duration and transcript timestamps refer to the saved audio, excluding paused time. Meeting date/time metadata is stored in UTC and displayed in the browser’s local timezone. Exports include the UTC offset.

## Features and failure recovery

- Dashboard: meeting count, captured time, action count, recent-first meeting cards, and full-text search.
- Durable storage: PCM WAV streamed to disk with a continually updated header; no entire meeting kept in RAM.
- Controls: one active recording globally, with validated start/pause/resume/stop transitions.
- Offline transcription: timestamped, language-detected faster-whisper transcription with voice activity detection.
- Local AI: structured JSON, exact source-quote validation, conservative missing-owner/deadline handling, and chunked processing of long transcripts. All chunks are processed; facts/actions are combined and summaries are reduced in stages.
- Details: Overview, Notes, and searchable Transcript tabs; saved-audio playback.
- Editing: structured note editing, add/remove action items, completion checkboxes, copy, and download.
- FTS5: searches title, transcript, notes, and action task/owner/deadline. Multiple terms use AND; tokens are literal, not FTS operators. Token search is not arbitrary substring matching.
- Exports: Markdown, TXT, DOCX, PDF, including title/date/duration, all note sections, important dates, and complete transcript. Export uses current saved edits. DOCX/PDF generation runs on your PC.
- Settings: local Ollama model, Whisper model, and storage/model paths. Settings persist in SQLite.

If Whisper fails, the recording stays intact and **Retry Transcription** appears. If Ollama fails, both recording and transcript remain available and **Retry AI Summary** appears. A disconnected audio device stops capture and preserves partial audio. On restart, unfinished jobs/recordings become recoverable states rather than showing a phantom recording forever. CPU processing jobs are serialized to reduce memory pressure.

Closing the browser does not stop capture; reopen the app to access controls. Closing the backend stops capture; restart and retry transcription to process what was saved. A hard power failure can still lose the last buffered frames. Do not delete a meeting unless you intend to permanently delete its recording and text files; the UI asks for confirmation.

## Storage and backups

```text
data/
├── recordings/      # <meeting UUID>.wav
├── transcripts/     # timestamped JSON and TXT
├── notes/           # editable structured JSON and Markdown
└── database/        # meetnotes.sqlite3, SQLite WAL files, server lock
```

SQLite has `meetings`, `action_items`, `decisions`, `settings`, and the `meeting_search` FTS5 table. Foreign keys are enabled on every connection and related rows cascade on deletion. Notes edits update the database, action rows, decisions, search index, and local note files.

To change storage location, stop the backend, copy the **entire** data folder to the new location, set `MEETNOTES_DATA_DIR` in `backend/.env`, then restart. Existing file references are relative to the data directory. Starting with an empty destination intentionally creates an empty library. Back up the entire folder while the backend is stopped, including the database. No cloud backups are created by the app.

Configuration:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MEETNOTES_DATA_DIR` | `../data` | Recordings, transcripts, notes, database |
| `MEETNOTES_MODEL_DIR` | `./models` | Offline Whisper models |
| `MEETNOTES_OLLAMA_URL` | `http://127.0.0.1:11434` | Loopback-only Ollama server |
| `MEETNOTES_PDF_FONT` | Windows Arial, detected | Optional TrueType font with needed language glyphs |

Relative paths resolve from `backend/`, independent of the current working directory. Restart the backend after changing environment variables. Data is local plaintext, not encrypted by this app; use your Windows account’s disk protections if needed. The backend binds to loopback and rejects unrelated browser origins/hosts. It is a personal local app, not an authenticated network service: do not expose it through a tunnel or public bind address.

## API

All endpoints use `/api`. Requests/responses use Pydantic validation for meetings, notes, transcripts, devices, and settings.

| Method | Route | Purpose |
| --- | --- | --- |
| GET / POST | `/meetings` | List / create |
| GET / DELETE | `/meetings/{id}` | Detail / permanently delete |
| POST | `/meetings/{id}/start` | `{ "device_id": 19, "consent_confirmed": true }` (use an ID from `/devices`) |
| POST | `/meetings/{id}/pause`, `/resume`, `/stop` | Recording controls |
| POST | `/meetings/{id}/transcribe` | Retry saved recording processing |
| POST | `/meetings/{id}/generate-notes` | Retry or regenerate AI notes |
| GET | `/meetings/{id}/transcript` | Timestamped transcript |
| GET / PUT | `/meetings/{id}/notes` | Read / edit structured notes |
| GET | `/meetings/{id}/audio` | Saved WAV, after stopping |
| GET | `/meetings/{id}/export?format=md` | `md`, `txt`, `docx`, `pdf` |
| GET | `/search?q=API` | Literal-token full-text search |
| GET | `/devices` | WASAPI loopback/microphone inputs |
| GET / PUT | `/settings` | Persistent settings |
| GET | `/system`, `/health` | Model availability / backend health |

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Cannot reach MeetNotes | Start `backend/run.py`; check port 8000. In development use port 5173, not `npm run preview`. |
| Ollama is not running | Start the tray app or `ollama serve`; check `ollama list`; refresh Settings; retry AI Summary. |
| Model not listed | Run `ollama pull llama3.2:3b`, then refresh Settings. Cloud models are intentionally rejected. |
| Whisper model unavailable | Run `python download_model.py base` from the activated backend environment, or download the model selected in Settings. |
| No speech detected | Play the saved WAV in the Transcript tab. Check that the selected loopback matches Meet’s speaker device. A silent/wrong input cannot be repaired by transcription. |
| Audio source unavailable | Connect/enable the device, close apps using exclusive mode, click Refresh, and choose another source. Run `python -m pyaudiowpatch` to list Windows devices. |
| Microphone unavailable | Allow desktop apps to use the microphone in Windows Settings → Privacy & security → Microphone. |
| Device disconnects / dropped frames | Partial audio is retained. Retry transcription for that part, then start a new meeting with a working source. |
| DLL load error | Install the official Microsoft Visual C++ 2015–2022 x64 redistributable and use 64-bit Python. |
| Python installation fails | Use a supported 64-bit Python with compatible wheels (3.11–3.13); upgrade pip inside the project venv. |
| Very slow processing / memory pressure | Choose Whisper tiny/base and Ollama llama3.2:1b; close other heavy apps. Models load locally and long meetings may take substantial time. |
| AI output invalid / unsupported quote | Transcript/audio are preserved. Retry, or use another installed model. You may edit notes manually after transcription. |
| Empty/missing note owner or deadline | `Not specified` is intentional; the app does not guess. |
| Interrupted meeting after restart | Open it and use Retry Transcription or Retry AI Summary. Saved files are retained. |
| PDF missing glyphs | Set `MEETNOTES_PDF_FONT` to a TrueType font covering the transcript’s language and restart. DOCX/TXT are alternatives for scripts requiring specialized shaping. |
| Disk full / large recordings | Free disk space before recording. PCM stereo at 48 kHz is about 690 MB/hour. Capture stops before WAV’s 4 GB limit (at 3.5 GB) and preserves the partial file. |
| Another backend owns the data | Close the existing MeetNotes backend normally; run a single process. Do not delete the lock file while another process is using it. |

## Verification

See [VERIFICATION.md](VERIFICATION.md) for completed checks and remaining real-device/model acceptance checks. `backend/requirements-lock.txt` captures the tested Windows/Python 3.13 dependency versions; use `pip install -r requirements-lock.txt` for that exact environment, or the standard requirements for other supported Python versions.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
cd ../frontend
npm run build
```

Tests use temporary storage and simulated audio/AI adapters for repeatable state-machine, processing-failure, retry, search, export, deletion, local-origin, and recovery checks. They do not record your microphone or depend on downloaded AI models. They do not establish transcription/summary accuracy on real meetings. For a first-use acceptance check, record a short consented conversation, pause/resume/stop, listen to the WAV, inspect timestamps, edit an action, search for it, and open each export.

## Project structure

```text
frontend/src/
  components/       shared UI
  pages/            Dashboard, Setup, Meeting, Settings
  services/         API and download helpers
  hooks/            cancellable polling
backend/app/
  main.py           loopback API, lifecycle, single-process lock
  config.py         paths and privacy boundary
  database.py       SQLite schema, persistence, FTS5
  schemas.py        validated request/response/notes types
  routes/api.py     HTTP endpoints
  services/
    audio.py        modular WASAPI PCM capture
    transcription.py   offline faster-whisper
    ollama.py       local structured extraction and chunking
    jobs.py         recording lifecycle, background jobs, recovery
    notes.py        Markdown rendering
    storage.py      safe paths and atomic text writes
    export.py      Markdown/TXT/DOCX/PDF
backend/tests/      isolated integration tests
```

No accounts, calendar automation, cloud sync, browser extension, advanced speaker identification, vector database, RAG, or agent framework. Notes are AI-assisted, not guaranteed facts: source-quote checking reduces fabricated material but cannot prove semantic correctness. Review names, commitments, and deadlines against the recording/transcript.

Implementation references: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [PyAudioWPatch loopback example](https://github.com/s0d3s/PyAudioWPatch/blob/master/examples/pawp_record_wasapi_loopback.py), [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
