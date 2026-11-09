# Autonomous Media Engine (AME)

Local-first AI-assisted YouTube Shorts / Instagram Reels creator for Windows.

## Current pipeline
- RSS topic discovery and local Ollama script drafting (Gemma 3 4B)
- English-first 30–45 second scripts with manual approval
- Fully local Piper neural English narration (no API key; CPU inference)

- **Real vertical stock-video clips from Pexels or Pixabay** when a provider API key is configured
- Fallback: Wikimedia Commons / publisher still images animated with a slow camera move
- FFmpeg clip normalization, crossfade transitions, word-timed karaoke captions (ElevenLabs alignment), and loudness mastering
- 1080 × 1920, 30 FPS MP4 output

## Local voice setup

AME now uses Piper locally instead of ElevenLabs or Edge TTS. No subscription, API key, or internet connection is needed after the voice model is downloaded. The initial default is the US English Ryan high-quality voice.

Run once in PowerShell:

```powershell
.\\scripts\\setup_tts.ps1
```

Or manually:

```powershell
pip install -r requirements.txt
python -m piper.download_voices --data-dir models/voices en_US-ryan-high
```

The model is stored under `models/voices/` and is ignored by Git. Adjust `PIPER_LENGTH_SCALE`, `PIPER_NOISE_SCALE`, and `PIPER_NOISE_W_SCALE` in `.env` to tune pacing and variation. Piper is CPU-friendly and offline. It sounds more natural than classic Windows SAPI, but does not have ElevenLabs-style emotion controls; script punctuation and sentence phrasing still matter.

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
PIPER_MODEL_PATH=./models/voices/en_US-ryan-high.onnx
PIPER_LENGTH_SCALE=0.94
PIPER_NOISE_SCALE=0.72
PIPER_NOISE_W_SCALE=0.78
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
- ElevenLabs character timestamps are grouped into compact 2–3 word karaoke captions. Edge TTS fallback uses estimated word timing.
- Review script facts, clip relevance, source pages and license terms before publishing.
- No automatic YouTube/Instagram publishing is implemented.


## Expressive ElevenLabs narration (recommended)

Set these in your local `.env` (never commit your API key):

```env
ELEVENLABS_API_KEY=your_key
ELEVENLABS_VOICE_ID=your_selected_voice_id
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_STABILITY=0.38
ELEVENLABS_SIMILARITY=0.78
ELEVENLABS_STYLE=0.35
ELEVENLABS_SPEED=1.06
```

Get an API key and choose a voice in your ElevenLabs account: https://elevenlabs.io/app/settings/api-keys and https://elevenlabs.io/app/voice-library. The voice ID is available in the voice details. AME calls the official text-to-speech-with-timestamps endpoint, so it can save character timing for synchronized captions. API usage consumes credits; check your current plan and credit balance before rendering. If the ElevenLabs key or voice ID is absent, AME falls back to Edge TTS.

ElevenLabs settings: lower stability adds variation; style exaggeration is supported by v2/v3 models; speaker boost improves clarity/similarity. These are starting values, not a guarantee of a particular performance. Preview a selected voice before committing credits.
