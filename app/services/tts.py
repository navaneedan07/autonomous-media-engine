"""ElevenLabs expressive TTS with character-level timing; Edge TTS fallback.

Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in the local .env.
The API key is never stored in source control.
"""
import base64
import json
import os
from pathlib import Path
import httpx

API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
STABILITY = float(os.getenv("ELEVENLABS_STABILITY", "0.38"))
SIMILARITY = float(os.getenv("ELEVENLABS_SIMILARITY", "0.78"))
STYLE = float(os.getenv("ELEVENLABS_STYLE", "0.35"))
SPEED = float(os.getenv("ELEVENLABS_SPEED", "1.06"))


def synthesize_speech(text: str, output_path: str) -> dict:
    if not text or not text.strip():
        raise ValueError("Narration is empty.")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    alignment_path = target.with_suffix(".alignment.json")

    if API_KEY and VOICE_ID:
        payload = {
            "text": text.strip(),
            "model_id": MODEL_ID,
            "output_format": "mp3_44100_128",
            "voice_settings": {
                "stability": max(0.0, min(1.0, STABILITY)),
                "similarity_boost": max(0.0, min(1.0, SIMILARITY)),
                "style": max(0.0, min(1.0, STYLE)),
                "speed": max(0.7, min(1.2, SPEED)),
                "use_speaker_boost": True,
            },
        }
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps"
        try:
            response = httpx.post(url, headers={"xi-api-key": API_KEY},
                                  json=payload, timeout=180)
            if response.status_code >= 400:
                detail = response.text[:1200]
                raise RuntimeError(f"ElevenLabs API {response.status_code}: {detail}")
            data = response.json()
            audio = data.get("audio_base64")
            alignment = data.get("alignment") or data.get("normalized_alignment")
            if not audio:
                raise RuntimeError("ElevenLabs response did not include audio_base64.")
            target.write_bytes(base64.b64decode(audio))
            if alignment:
                alignment_path.write_text(json.dumps(alignment, ensure_ascii=False),
                                          encoding="utf-8")
            if target.stat().st_size < 1000:
                raise RuntimeError("ElevenLabs returned an unexpectedly small audio file.")
            return {"provider": "elevenlabs", "audio_path": str(target),
                    "alignment_path": str(alignment_path) if alignment else None,
                    "voice_id": VOICE_ID, "model_id": MODEL_ID}
        except httpx.HTTPError as exc:
            raise RuntimeError(f"ElevenLabs request failed: {exc}") from exc

    # Keep the app usable before the user configures ElevenLabs credentials.
    try:
        import asyncio
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("Configure ElevenLabs credentials or install edge-tts.") from exc
    async def _save():
        communicate = edge_tts.Communicate(
            text=text.strip(),
            voice=os.getenv("AME_TTS_VOICE", "en-US-ChristopherNeural"),
            rate=os.getenv("AME_TTS_RATE", "+8%"),
            pitch=os.getenv("AME_TTS_PITCH", "+2Hz"),
            volume=os.getenv("AME_TTS_VOLUME", "+0%"),
        )
        await communicate.save(str(target))
    try:
        asyncio.run(_save())
    except RuntimeError as exc:
        raise RuntimeError(f"Fallback neural TTS failed: {exc}") from exc
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError("Fallback TTS did not produce an audio file.")
    return {"provider": "edge-tts", "audio_path": str(target),
            "alignment_path": None, "voice_id": None, "model_id": None}
