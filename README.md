# Autonomous Media Engine (AME)

Local-first AI-assisted short-form content engine for Windows.

## Current capabilities
- RSS-based topic discovery with heuristic scoring
- Local Ollama script generation (Gemma 3 4B default)
- English-first 30–45 second script drafts
- SQLite storage and explicit human approval/rejection
- Offline Windows SAPI text-to-speech through pyttsx3
- Locally generated portrait motion-graphic scene cards
- FFmpeg MP4 assembly at 1080 × 1920, 30 FPS

**Important:** the first renderer produces clean text-based motion-graphic cards with a local system voice. It does not generate photorealistic footage or source images. Review all claims and source links before approving. Social publishing is not implemented.

## Windows setup

Requirements: Windows 10/11, Python 3.11+, Ollama, and FFmpeg available on PATH.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Install Ollama from https://ollama.com and download the model:

```powershell
ollama pull gemma3:4b
ollama serve
```

Install FFmpeg and ensure `ffmpeg -version` works in PowerShell. The TTS adapter uses installed Windows speech voices (SAPI); no cloud TTS API key is needed.

Edit `.env` if necessary. Defaults:
- `OLLAMA_MODEL=gemma3:4b`
- `CONTENT_LANGUAGE=english`
- `VIDEO_MIN_SECONDS=30`
- `VIDEO_MAX_SECONDS=45`
- `VIDEO_WIDTH=1080`, `VIDEO_HEIGHT=1920`, `VIDEO_FPS=30`
- `VIDEO_OUTPUT_DIR=./output`

Start the API:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: http://127.0.0.1:8000/docs

## Workflow

1. Discover topics: `POST /research/discover`
2. List topics: `GET /topics`
3. Generate script: `POST /videos/generate/{topic_id}`
4. Inspect script: `GET /videos/{video_id}`
5. Approve only after reviewing: `POST /videos/{video_id}/approve`
6. Render approved video: `POST /videos/{video_id}/render`
7. Retrieve output path from the response. Files are written under `output/video_{id}/`.

Example PowerShell render call:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/videos/1/render" |
    ConvertTo-Json -Depth 5
```

The render endpoint refuses drafts that are not approved. Rendering requires FFmpeg and Windows SAPI voices. If your existing approved script was generated before the English default was set, it remains unchanged; generate a new script to use the English prompt.

## Notes and limitations
- Existing local `.env` values override `.env.example`; update `CONTENT_LANGUAGE=english` manually if your local file still says bilingual.
- RSS topic scoring is a basic heuristic, not validated market research.
- The first visual style is text-card motion graphics, not generated stock footage or video.
- TTS voice quality depends on Windows voices installed on the machine.
- No automatic YouTube/Instagram publishing is implemented.
- Verify factual claims against original sources and use only media you have rights to use.
