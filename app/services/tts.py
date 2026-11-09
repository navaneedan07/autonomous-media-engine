"""Offline text-to-speech using installed Windows SAPI voices."""
import platform
from pathlib import Path


def synthesize_speech(text: str, output_path: str) -> str:
    if platform.system() != "Windows":
        raise RuntimeError("The initial offline TTS adapter requires Windows SAPI.")
    if not text or not text.strip():
        raise ValueError("Narration is empty.")
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("pyttsx3 is missing. Run: pip install -r requirements.txt") from exc
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = pyttsx3.init("sapi5")
    engine.setProperty("rate", 168)
    engine.setProperty("volume", 1.0)
    engine.save_to_file(text.strip(), str(target))
    engine.runAndWait()
    engine.stop()
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError("Windows TTS did not create audio. Check installed Windows speech voices.")
    return str(target)
