"""Conservative stock-footage matching with optional local CLIP frame scoring.

The optional CLIP model evaluates sampled frames, not just provider tags. Without
CLIP installed, AME falls back to conservative metadata overlap and reports that
limitation in the render manifest.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path

import httpx
from PIL import Image

STOP = set("""a an the to for from and or of in on at with by into over under
close up cinematic montage scene shot showing working navigating illustrating
future video footage visual logo image animation smoothly efficiently complex
new latest technology technological applications integrated systems next room
""".split())
SYNONYMS = {
    "robot": {"robot", "robotic", "robots", "robotics", "humanoid"},
    "chip": {"chip", "chips", "semiconductor", "semiconductors", "processor", "microchip"},
    "factory": {"factory", "manufacturing", "industrial", "assembly"},
    "home": {"home", "house", "apartment", "living", "room", "interior"},
    "hospital": {"hospital", "medical", "healthcare", "doctor", "nurse"},
    "computer": {"computer", "laptop", "desktop", "pc", "technology"},
}

_CLIP = None


def keywords(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (value or "").lower())
            if len(w) > 2 and w not in STOP}


def queries(visual: str, topic: str = "") -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", (visual or "").lower())
             if w not in STOP and len(w) > 2 and w not in {"samsung", "cleanbot"} and not w.endswith("bot")]
    result = [" ".join(words[:4]), " ".join(words[:2])]
    return list(dict.fromkeys(q for q in result if q))


def relevance(visual: str, tags: str, width: int, height: int) -> float:
    wanted, found = keywords(visual), keywords(tags)
    if not wanted or not found:
        return 0.0
    expanded = set(wanted)
    for group in SYNONYMS.values():
        if wanted & group:
            expanded.update(group)
    overlap = len(expanded & found) / max(1, min(5, len(expanded)))
    portrait = 0.06 if height > width else 0.0
    hd = 0.04 if min(width, height) >= 720 else 0.0
    return min(1.0, overlap * 0.90 + portrait + hd)


def _clip_model():
    global _CLIP
    if _CLIP is not None:
        return _CLIP
    from transformers import CLIPModel, CLIPProcessor
    import torch
    model_name = os.getenv("AME_CLIP_MODEL", "openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    model.eval()
    _CLIP = (processor, model, torch)
    return _CLIP


def _sample_frames(video_url: str, directory: Path) -> list[Image.Image]:
    """Sample three frames directly from a provider URL; do not download full clips."""
    frames = []
    for index, seconds in enumerate((1.0, 3.0, 5.0)):
        target = directory / f"ame_frame_{index}.jpg"
        result = subprocess.run(
            [os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", "-ss", str(seconds),
             "-i", video_url, "-frames:v", "1", "-vf", "scale=384:-1",
             str(target)], capture_output=True, text=True, timeout=35)
        if result.returncode == 0 and target.exists():
            try:
                with Image.open(target) as image:
                    frames.append(image.convert("RGB").copy())
            finally:
                target.unlink(missing_ok=True)
    return frames


def score_video_candidate(query: str, description: str, width: int,
                          height: int, url: str) -> float:
    """Download a small candidate set and rank actual sampled frames with CLIP.

    If the optional model is unavailable, use metadata overlap as a conservative
    fallback. This fallback is not visual verification.
    """
    metadata_score = relevance(query, description, width, height)
    if os.getenv("AME_CLIP_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return metadata_score
    try:
        with tempfile.TemporaryDirectory(prefix="ame_clip_") as directory:
            frames = _sample_frames(url, Path(directory))
            if not frames:
                return metadata_score
            processor, model, torch = _clip_model()
            inputs = processor(text=[query], images=frames, return_tensors="pt",
                               padding=True, truncation=True)
            with torch.inference_mode():
                outputs = model(**inputs)
                image_embeds = torch.nn.functional.normalize(outputs.image_embeds, dim=-1)
                text_embeds = torch.nn.functional.normalize(outputs.text_embeds, dim=-1)
                cosine = image_embeds @ text_embeds.T
                similarity = float(cosine.max().item())
            # CLIP cosine similarities for stock footage commonly occupy a
            # narrow range. Map to a bounded ranking score, not a probability.
            visual_score = max(0.0, min(1.0, (similarity - 0.15) / 0.25))
            return max(0.0, min(1.0, visual_score * 0.9 + metadata_score * 0.1))
    except Exception:
        return metadata_score
