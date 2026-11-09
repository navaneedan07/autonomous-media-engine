"""Fully local Piper neural TTS. No cloud API, account, or API key required."""
import os
from pathlib import Path
import wave

MODEL_PATH = Path(os.getenv(
    "PIPER_MODEL_PATH",
    "models/voices/en_US-ryan-high.onnx",
))


def synthesize_speech(text: str, output_path: str) -> dict:
    if not text or not text.strip():
        raise ValueError("Narration is empty.")
    if not MODEL_PATH.exists():
        raise RuntimeError(
            f"Local Piper voice model not found: {MODEL_PATH}. "
            "Run: powershell -ExecutionPolicy Bypass -File scripts/setup_tts.ps1"
        )
    try:
        from piper import PiperVoice, SynthesisConfig
    except ImportError as exc:
        raise RuntimeError("Piper is not installed. Run: pip install -r requirements.txt") from exc

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Slightly faster pacing and natural variation. Piper is a compact local
    # neural voice; it does not provide ElevenLabs-style emotion controls.
    syn_config = SynthesisConfig(
        volume=1.0,
        length_scale=float(os.getenv("PIPER_LENGTH_SCALE", "1.16")),
        noise_scale=float(os.getenv("PIPER_NOISE_SCALE", "0.72")),
        noise_w_scale=float(os.getenv("PIPER_NOISE_W_SCALE", "0.78")),
        normalize_audio=True,
    )
    voice = PiperVoice.load(str(MODEL_PATH), use_cuda=False)
    with wave.open(str(target), "wb") as wav_file:
        voice.synthesize_wav(text.strip(), wav_file, syn_config=syn_config)
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError("Piper did not produce a valid WAV file.")
    return {
        "provider": "piper-local",
        "audio_path": str(target.resolve()),
        "model_path": str(MODEL_PATH.resolve()),
        "voice": MODEL_PATH.stem,
        "offline": True,
    }
