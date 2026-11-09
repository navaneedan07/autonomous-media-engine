# Autonomous Media Engine (AME)

Local-first AI-assisted YouTube Shorts / Instagram Reels creator for Windows.

## Current pipeline
- RSS topic discovery and local Ollama script drafting (Gemma 3 4B)
- English-first 30–45 second scripts with manual approval
- Expressive neural English narration using Edge TTS (internet required, no paid API key)
- **Real vertical stock-video clips from Pexels or Pixabay** when a provider API key is configured
- Fallback: Wikimedia Commons / publisher still images animated with a slow camera move
- FFmpeg clip normalization, montage, and burned-in sentence captions
- 1080 × 1920, 30 FPS MP4 output

## Stock video API setup

Pexels has temporarily paused new API-key issuance. Use Pixabay as the alternative:

1. Create/sign in to a Pixabay account: https://pixabay.com/accounts/register/
2. Open the API documentation/account page: https://pixabay.com/api/docs/
3. Copy your API key into your local `.env`:

```env
PIXABAY_API_KEY=your_key_here
```

Pixabay asks API users to cache results for 24 hours, avoid mass automated queries, and credit the source when displaying results. AME searches per scene and downloads selected video files locally. Review Pixabay's current Content License before publishing.

### Pexels (optional)

## Get the free Pexels API key

1. Create/sign in to a Pexels account: https://www.pexels.com/
2. Request an API key: https://www.pexels.com/api/
3. Put the key in your local `.env`:

```env
PEXELS_API_KEY=your_key_here
```

The key stays on your computer and must not be committed to GitHub. Pexels API access is subject to Pexels' current rate limits and license terms. The renderer records source pages in `attributions.json`.

If neither key is configured, AME falls back to still images. The render response reports `pexels_enabled` and `pixabay_enabled`.

## Windows setup

Requirements: Windows 10/11, Python 3.11+, Ollama, FFmpeg on PATH, internet access.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Install Ollama and pull the model:

```powershell
ollama pull gemma3:4b
ollama serve
```

Install FFmpeg. The build should include the `subtitles` filter (libass); verify with:

```powershell
ffmpeg -filters | findstr subtitles
```

Set local `.env` values:

```env
OLLAMA_MODEL=gemma3:4b
CONTENT_LANGUAGE=english
AME_TTS_VOICE=en-US-ChristopherNeural
AME_TTS_RATE=+8%
AME_TTS_PITCH=+2Hz
AME_TTS_VOLUME=+0%
PEXELS_API_KEY=
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_FPS=30
```

Start API:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Docs: http://127.0.0.1:8000/docs

## Workflow

1. Discover: `POST /research/discover`
2. List topics: `GET /topics`
3. Generate: `POST /videos/generate/{topic_id}`
4. Review: `GET /videos/{video_id}`
5. Approve: `POST /videos/{video_id}/approve`
6. Render: `POST /videos/{video_id}/render`

Output: `output/video_{id}/` including source clips, narration, captions, final MP4 and `attributions.json`.

A previously rendered video must be approved again before re-rendering.

## Important limitations
- Real stock footage requires a Pexels API key and internet access. Matching clips are not guaranteed for every scene.
- The fallback uses still images; it does not fabricate them as video footage.
- Captions are sentence-timed approximations across the voice track, not phoneme-perfect word-level karaoke captions.
- Review script facts, clip relevance, source pages and license terms before publishing.
- No automatic YouTube/Instagram publishing is implemented.
