"""Deterministic stock-footage query planner and metadata relevance scoring.

No large model required. Reject misleading entity-specific footage and rank
provider tags using overlap with concise visual concepts.
"""
import re

STOP = set("""a an the to for from and or of in on at with by into over under
close up cinematic montage scene shot showing working navigating illustrating
future video footage visual logo image animation smoothly efficiently complex
new latest technology technological applications integrated systems next room
""".split())

def keywords(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (value or "").lower())
            if len(w) > 2 and w not in STOP}

def queries(visual: str, topic: str) -> list[str]:
    # Specific named products often have no corresponding generic stock clip.
    # Use the underlying object/action rather than fabricating the named product.
    visual_words = keywords(visual)
    terms = [w for w in re.findall(r"[a-z0-9]+", visual.lower())
             if w in visual_words and not (w.endswith("bot") or w in {"samsung", "cleanbot"})]
    primary = " ".join(terms[:4])
    generic = " ".join(terms[:2])
    return list(dict.fromkeys(q for q in (primary, generic) if q))

def relevance(visual: str, tags: str, width: int, height: int) -> float:
    wanted, found = keywords(visual), keywords(tags)
    if not wanted or not found:
        return 0.0
    overlap = len(wanted & found) / max(1, min(5, len(wanted)))
    portrait = 0.12 if height > width else 0.0
    hd = 0.08 if min(width, height) >= 720 else 0.0
    return min(1.0, overlap + portrait + hd)
