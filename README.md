# Autonomous Media Engine (AME)

Local-first AI-assisted short-form content engine for Windows.

## Current capabilities
- RSS topic discovery and local Ollama script drafting (Gemma 3 4B)
- English-first 30–45 second scripts and human approval
- Expressive neural English narration using Edge TTS (free endpoint, internet required, no API key)
- Article lead-image extraction and Wikimedia Commons image search
- Full-frame image montage with slow zoom/pan and restrained lower-third captions
- FFmpeg MP4 export at 1080 × 1920, 30 FPS

**Visual limitation:** this build uses photographs/images, not generated cinematic video clips. It animates them with camera movement to avoid the previous PowerPoint-style text cards. Wikimedia Commons attribution/license metadata is saved to `attributions.json`; publisher images may have reuse restrictions. Check rights before publishing. No social auto-publishing is implemented.

## Windows setup

Requirements: Windows 10/11, Python 3.11+, Ollama, FFmpeg on PATH, and internet access for neural TTS and image retrieval.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Install Ollama and download the model:

```powershell
ollama pull gemma3:4b
ollama serve
```

Ensure `ffmpeg -version` works in PowerShell.

Defaults in `.env`:
- `OLLAMA_MODEL=gemma3:4b`
- `CONTENT_LANGUAGE=english`
- `AME_TTS_VOICE=en-US-ChristopherNeural`
- `AME_TTS_RATE=+8%`
- `AME_TTS_PITCH=+2Hz`
- `VIDEO_WIDTH=1080`, `VIDEO_HEIGHT=1920`, `VIDEO_FPS=30`

Optional voice tuning: `AME_TTS_VOICE`, `AME_TTS_RATE`, `AME_TTS_PITCH`, `AME_TTS_VOLUME`. Voice availability and delivery vary; preview before publishing.

Start the API:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: http://127.0.0.1:8000/docs

## Workflow

1. `POST /research/discover`
2. `GET /topics`
3. `POST /videos/generate/{topic_id}`
4. Review `GET /videos/{video_id}`
5. Approve: `POST /videos/{video_id}/approve`
6. Render: `POST /videos/{video_id}/render`

Output is written under `output/video_{id}/`, including narration audio, downloaded assets, rendered MP4, and `attributions.json`.

Example:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/videos/1/render" |
    ConvertTo-Json -Depth 5
```

Existing `.env` values override defaults. Set `CONTENT_LANGUAGE=english` manually if your local file still says bilingual.

## Limitations
- Wikimedia and article images are still images, not stock video footage or AI-generated footage.
- The Edge TTS endpoint is online, not fully local; no paid API key is required, but internet access is.
- RSS scoring is heuristic, not validated market research.
- Review claims, source URLs, and media licenses before publishing.
- No automatic YouTube/Instagram publishing is implemented.
