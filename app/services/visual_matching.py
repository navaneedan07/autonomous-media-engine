"""Stock-footage query planning and conservative metadata relevance scoring."""
import re

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

def keywords(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (value or "").lower())
            if len(w) > 2 and w not in STOP}

def queries(visual: str, topic: str = "") -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", (visual or "").lower())
             if w not in STOP and len(w) > 2 and w not in {"samsung", "cleanbot"} and not w.endswith("bot")]
    # Prefer concrete objects/actions. Never search a whole prose sentence.
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
    # Technical quality is a tie-breaker, not a substitute for semantic match.
    portrait = 0.06 if height > width else 0.0
    hd = 0.04 if min(width, height) >= 720 else 0.0
    return min(1.0, overlap * 0.90 + portrait + hd)
