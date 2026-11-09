# Autonomous Media Engine (AME)

Local-first AI-assisted YouTube Shorts / Instagram Reels production for Windows.

## Design goals

- Zero recurring video-generation/API spend.
- 30–45 second English short-form videos.
- 1080 × 1920, 30 FPS MP4 output.
- Local Ollama scripting and Piper narration.
- Real footage selected per narration scene; never silently substitute unrelated images.
- Human approval before publishing.

## Production pipeline

1. RSS discovery gathers candidate topics and source URLs.
2. Ollama (Gemma 3 4B by default) drafts a short script and 5–7 concrete, ordered visual beats.
3. Piper generates narration locally.
4. Pexels/Pixabay search retrieves multiple candidate clips for each scene.
5. Optional local CLIP evaluates sampled frames against each scene description and reranks candidates. Without CLIP, AME falls back to provider metadata/tags; this is weaker and is not visual verification.
6. FFmpeg normalizes clips, builds crossfades, burns word-timed captions, and masters audio.
7. The render is returned for human review. AME does not auto-publish.

## Windows setup

Requirements: Windows 10/11, Python 3.11+, Ollama, FFmpeg with libass support, and internet access for research/media retrieval.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Install Ollama and pull the local model:

```powershell
ollama pull gemma3:4b
ollama serve
```

Install FFmpeg and ensure it is on PATH. Confirm subtitle support:

```powershell
ffmpeg -filters | findstr subtitles
```

## Local narration

Run once:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_tts.ps1
```

Default voice: Piper `en_US-ryan-high`. Model files are stored in `models/voices/` and are ignored by Git. The voice is offline after download. It is CPU-friendly but less expressive than paid neural TTS services.

## Stock-video providers

At least one provider key is required for stock footage.

### Pixabay

1. Create/sign in at https://pixabay.com/
2. Obtain an API key from https://pixabay.com/api/docs/
3. Add it to your local `.env`:

```env
PIXABAY_API_KEY=your_key
```

Pixabay asks API users to cache results for 24 hours and avoid mass automated queries. Review its current Content License before publication.

### Pexels (optional)

Obtain a key at https://www.pexels.com/api/ and add:

```env
PEXELS_API_KEY=your_key
```

API availability, rate limits and license terms are controlled by Pexels. Keep keys in the local `.env`; never commit them.

## Optional: local semantic visual matching

For stronger scene-to-footage relevance, install the optional CPU CLIP stack:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_clip.ps1
```

This installs PyTorch and Transformers and can consume several GB of disk space. The first render downloads the CLIP model weights. It samples frames from candidate videos and compares them with the scene description. It does not prove factual correctness, and CPU ranking adds render time.

Settings:

```env
AME_CLIP_ENABLED=true
AME_CLIP_MODEL=openai/clip-vit-base-patch32
MIN_VISUAL_RELEVANCE=0.38
```

If installation is too heavy for the PC, set `AME_CLIP_ENABLED=false`. Metadata matching remains available but should be treated as a weaker fallback.

## Optional: word-level caption alignment

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_alignment.ps1
```

The first run downloads the `base.en` Whisper model. It runs on CPU with int8 quantization. If it is unavailable, AME uses estimated word timings; check captions carefully.

## Start AME

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: http://127.0.0.1:8000/docs

## Workflow

1. Discover topics: `POST /research/discover`
2. List topics: `GET /topics`
3. Generate a draft: `POST /videos/generate/{topic_id}`
4. Review the script: `GET /videos/{video_id}`
5. Approve: `POST /videos/{video_id}/approve`
6. Render: `POST /videos/{video_id}/render`

Output is written under `output/video_{id}/`, including source clips, narration, captions, final MP4 and `attributions.json`.

## Quality and limitations

- A missing unique clip causes the render to stop instead of filling the scene with unrelated footage.
- CLIP is a semantic similarity ranker, not a fact checker. Verify every scene and claim before publication.
- Stock availability and API quotas vary. No paid generative-video model is used.
- 1080p is the export profile; it does not mean the original source footage is native 1080p.
- Review each rendered video manually before publishing.
- Automatic YouTube/Instagram publishing is not implemented.
