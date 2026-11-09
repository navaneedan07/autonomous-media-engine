# Autonomous Media Engine (AME)

Local-first backend for AI-assisted bilingual English/Tamil short-form content research and script drafting.

## Included in this first build
- FastAPI backend
- SQLite database and schema initialization
- RSS topic discovery and heuristic niche/topic scoring
- Ollama local model integration
- Bilingual English/Tamil script generation (30-45 seconds)
- Draft listing and explicit approve/reject endpoints
- Importable n8n daily research + draft workflow

**No automatic publishing is implemented.** Approval only records a human decision. Video rendering, TTS and social publishing are later milestones.

## Windows setup

Requires Windows 10/11, Python 3.11+, Ollama. Node.js is optional for n8n.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Install Ollama from https://ollama.com, then:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

In another PowerShell window:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: http://127.0.0.1:8000/docs

## Test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ollama/status
Invoke-RestMethod -Method Post http://127.0.0.1:8000/research/discover
Invoke-RestMethod http://127.0.0.1:8000/topics
Invoke-RestMethod -Method Post http://127.0.0.1:8000/videos/generate/1
Invoke-RestMethod http://127.0.0.1:8000/videos
```

Approve a draft:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/videos/1/approve -ContentType "application/json" -Body '{"reason":"Reviewed manually"}'
```

## n8n workflow
Import `workflows/daily_research_and_draft.json` into local n8n. If n8n runs directly on Windows, `127.0.0.1` works. If n8n runs in Docker, change the API host to `host.docker.internal`. Test manually before activating the schedule.

## Configuration
Edit `.env`: model, Ollama URL, content language, duration bounds and RSS item limit.

## Important
RSS topic scoring is a basic heuristic, not validated market research. Always inspect source URLs and verify claims, especially health, finance, safety or scientific claims. Use original scripts and licensed media. Never assume AI-generated content automatically qualifies for monetization.
