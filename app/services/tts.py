"""Expressive neural English TTS using the free Edge speech endpoint.

Requires an internet connection; no API key is used. This replaces the robotic
Windows SAPI voice. Set AME_TTS_VOICE to another Edge voice if desired.
"""
import asyncio
import os
from pathlib import Path

DEFAULT_VOICE = os.getenv("AME_TTS_VOICE", "en-US-ChristopherNeural")
DEFAULT_RATE = os.getenv("AME_TTS_RATE", "+8%")
DEFAULT_PITCH = os.getenv("AME_TTS_PITCH", "+2Hz")
DEFAULT_VOLUME = os.getenv("AME_TTS_VOLUME", "+0%")


def synthesize_speech(text: str, output_path: str) -> str:
    if not text or not text.strip():
        raise ValueError("Narration is empty.")
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("edge-tts is missing. Run: pip install -r requirements.txt") from exc

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    async def _save():
        communicate = edge_tts.Communicate(
            text=text.strip(),
            voice=DEFAULT_VOICE,
            rate=DEFAULT_RATE,
            pitch=DEFAULT_PITCH,
            volume=DEFAULT_VOLUME,
        )
        await communicate.save(str(target))

    try:
        asyncio.run(_save())
    except RuntimeError as exc:
        # FastAPI's sync endpoint normally has no running event loop in this worker.
        raise RuntimeError(f"Neural TTS failed: {exc}") from exc
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError("Neural TTS did not produce an audio file.")
    return str(target)
