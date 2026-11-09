"""Render approved scripts into vertical Shorts using real stock video clips.

Pexels and Pixabay stock footage are searched per scene. Rendering fails closed
when a unique relevant clip cannot be found. FFmpeg handles voice-over, captions,
and final encoding.
"""
import json
import re
import subprocess
from pathlib import Path
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps
from app.config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_CODEC, VIDEO_CRF,
    VIDEO_PRESET, VIDEO_AUDIO_BITRATE, FFMPEG_BIN, VIDEO_OUTPUT_DIR,
)
from app.db import get_db
from app.services.tts import synthesize_speech
from app.services.visual_matching import queries, relevance

import os
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()


def export_profile():
    return {
        "format": "mp4", "orientation": "portrait",
        "width": VIDEO_WIDTH, "height": VIDEO_HEIGHT, "fps": VIDEO_FPS,
        "video_codec": VIDEO_CODEC, "crf": VIDEO_CRF, "preset": VIDEO_PRESET,
        "audio_codec": "aac", "audio_bitrate": VIDEO_AUDIO_BITRATE,
        "default_quality": "1080p" if (VIDEO_WIDTH, VIDEO_HEIGHT) == (1080, 1920) else "custom",
    }


def _font(size, bold=False):
    candidates = (["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/Arial.ttf"] if bold
                  else ["C:/Windows/Fonts/arial.ttf"])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _pexels_clip(query: str, destination: Path):
    """Search multiple phrase variants, then rank sampled frames with local CLIP."""
    if not PEXELS_API_KEY:
        return None
    try:
        from app.services.visual_matching import score_video_candidate
        candidates, seen = [], set()
        for search_query in queries(query):
            response = httpx.get(
                "https://api.pexels.com/videos/search",
                params={"query": search_query, "per_page": 12, "orientation": "portrait"},
                headers={"Authorization": PEXELS_API_KEY}, timeout=30,
            )
            response.raise_for_status()
            for video in response.json().get("videos", []):
                page = video.get("url", "")
                if not page or page in seen:
                    continue
                seen.add(page)
                files = [item for item in video.get("video_files", [])
                         if item.get("link") and (item.get("height") or 0) >= (item.get("width") or 0)
                         and (item.get("width") or 0) >= 720]
                if files:
                    item = max(files, key=lambda value: (value.get("width") or 0) * (value.get("height") or 0))
                    candidates.append((item["width"], item["height"], item["link"], page))
        if not candidates:
            return None
        ranked = []
        for width, height, link, page in candidates[:8]:
            score = score_video_candidate(query, page, width, height, link)
            if os.getenv("AME_CLIP_ENABLED", "true").lower() not in {"1", "true", "yes"}:
                # Pexels does not expose searchable tags in this response. The
                # search query is a weak relevance signal, not visual verification.
                score = max(score, 0.30)
            ranked.append((score, abs(width * height - 1080 * 1920), link, page))
        ranked.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        score, _, url, page = ranked[0]
        minimum = float(os.getenv("MIN_VISUAL_RELEVANCE", "0.28"))
        if score < minimum:
            return None
        with httpx.stream("GET", url, timeout=90, follow_redirects=True) as stream:
            stream.raise_for_status()
            with destination.open("wb") as f:
                for chunk in stream.iter_bytes(1024 * 1024):
                    f.write(chunk)
        if destination.exists() and destination.stat().st_size > 100_000:
            return {"provider": "Pexels", "page": page, "relevance_score": round(score, 3),
                    "search_queries": queries(query),
                    "matching_method": "CLIP sampled frames" if os.getenv("AME_CLIP_ENABLED", "true").lower() in {"1","true","yes"} else "metadata fallback",
                    "license": "Pexels license; review terms before publication"}
    except Exception:
        destination.unlink(missing_ok=True)
    return None



def _pixabay_clip(query: str, destination: Path):
    """Search several Pixabay phrases and rerank the best candidates."""
    if not PIXABAY_API_KEY:
        return None
    try:
        from app.services.visual_matching import score_video_candidate
        candidates, seen = [], set()
        for search_query in queries(query):
            response = httpx.get(
                "https://pixabay.com/api/videos/",
                params={"key": PIXABAY_API_KEY, "q": search_query, "per_page": 20,
                        "safesearch": "true", "min_width": 720},
                timeout=30,
            )
            response.raise_for_status()
            for hit in response.json().get("hits", []):
                page = hit.get("pageURL", "")
                if not page or page in seen:
                    continue
                seen.add(page)
                variants = [((hit.get("videos") or {}).get(name) or {})
                            for name in ("large", "medium", "small", "tiny")]
                variants = [item for item in variants if item.get("url")
                            and (item.get("width") or 0) >= 720
                            and (item.get("height") or 0) >= 720]
                if not variants:
                    continue
                item = max(variants, key=lambda value: (value.get("width") or 0) * (value.get("height") or 0))
                candidates.append((item["width"], item["height"], item["url"], page, hit.get("tags", "")))
        if not candidates:
            return None
        # Use tag overlap to shortlist before the more expensive frame analysis.
        candidates.sort(key=lambda item: relevance(query, item[4], item[0], item[1]), reverse=True)
        ranked = []
        for width, height, url, page, tags in candidates[:8]:
            score = score_video_candidate(query, tags, width, height, url)
            ranked.append((score, abs(width * height - 1080 * 1920), url, page, tags))
        ranked.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        score, _, url, page, tags = ranked[0]
        minimum = float(os.getenv("MIN_VISUAL_RELEVANCE", "0.28"))
        if score < minimum:
            return None
        with httpx.stream("GET", url, timeout=90, follow_redirects=True) as stream:
            stream.raise_for_status()
            with destination.open("wb") as output:
                for chunk in stream.iter_bytes(1024 * 1024):
                    output.write(chunk)
        if destination.exists() and destination.stat().st_size > 100_000:
            return {"provider": "Pixabay", "page": page, "tags": tags,
                    "relevance_score": round(score, 3), "search_queries": queries(query),
                    "matching_method": "CLIP sampled frames" if os.getenv("AME_CLIP_ENABLED", "true").lower() in {"1","true","yes"} else "metadata fallback",
                    "license": "Pixabay Content License; review current terms"}
    except Exception:
        destination.unlink(missing_ok=True)
    return None



def _download_image(url: str, path: Path) -> bool:
    try:
        response = httpx.get(url, timeout=25, follow_redirects=True,
                             headers={"User-Agent": "AutonomousMediaEngine/0.2"})
        response.raise_for_status()
        path.write_bytes(response.content)
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        path.unlink(missing_ok=True)
        return False


def _article_image(article_url: str, work: Path):
    if not article_url:
        return None
    try:
        html = httpx.get(article_url, timeout=20, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"}).text[:2_000_000]
        match = re.search(r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image)["'][^>]+content=["']([^"']+)""", html, re.I)
        if match:
            path = work / "article_image.jpg"
            if _download_image(match.group(1).replace("&amp;", "&"), path):
                return path
    except Exception:
        pass
    return None


def _commons_image(query: str, path: Path):
    try:
        params = {"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
                  "gsrnamespace": 6, "gsrlimit": 6, "prop": "imageinfo",
                  "iiprop": "url|extmetadata", "iiurlwidth": 1200, "format": "json"}
        data = httpx.get("https://commons.wikimedia.org/w/api.php", params=params, timeout=25).json()
        for page in data.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if url and _download_image(url, path):
                meta = info.get("extmetadata", {})
                return path, {"provider": "Wikimedia Commons", "title": page.get("title", ""),
                              "license": (meta.get("LicenseShortName") or {}).get("value", "Check license"),
                              "artist": (meta.get("Artist") or {}).get("value", "")}
    except Exception:
        pass
    return None, None


def _caption_card(image_path: Path, output: Path, caption: str):
    with Image.open(image_path) as src:
        image = ImageOps.fit(src.convert("RGB"), (VIDEO_WIDTH, VIDEO_HEIGHT),
                             method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((42, VIDEO_HEIGHT - 300, VIDEO_WIDTH - 42, VIDEO_HEIGHT - 95),
                           radius=28, fill=(0, 0, 0, 155))
    font = _font(48, True)
    words, lines, line = caption.split(), [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] < VIDEO_WIDTH - 140:
            line = trial
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    y = VIDEO_HEIGHT - 250
    for item in lines[:2]:
        draw.text((75, y), item, font=font, fill="white", stroke_width=1, stroke_fill="black")
        y += 62
    Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB").save(output, quality=92)


def _run(command, label):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{label} timed out after 15 minutes.") from exc
    if result.returncode:
        raise RuntimeError(f"{label} failed: {(result.stderr or '')[-2200:]}")


def render_approved_video(video_id: int) -> dict:
    with get_db() as db:
        row = db.execute("""SELECT v.id,v.status,v.duration_target_seconds,s.narration,
            s.scene_plan,s.title,t.title AS topic_title,t.url AS topic_url
            FROM videos v JOIN scripts s ON s.id=v.script_id
            JOIN topics t ON t.id=v.topic_id WHERE v.id=?""", (video_id,)).fetchone()
    if not row:
        raise ValueError("Video not found")
    if row["status"] != "approved":
        raise ValueError("Only approved videos can be rendered. Approve the draft first.")
    narration = (row["narration"] or "").strip()
    if not narration:
        raise ValueError("The approved script has no narration.")

    work = VIDEO_OUTPUT_DIR / f"video_{video_id}"
    work.mkdir(parents=True, exist_ok=True)
    audio_path = work / "narration.wav"
    synthesize_speech(narration, str(audio_path))
    try:
        scenes = json.loads(row["scene_plan"] or "[]")
    except json.JSONDecodeError:
        scenes = []
    if not isinstance(scenes, list) or not scenes:
        scenes = [{"visual": row["topic_title"], "on_screen_text": row["topic_title"]}]
    scenes = scenes[:10]
    clip_files, attributions = [], []
    used_sources = set()
    unmatched_scenes = []

    for index, scene in enumerate(scenes, 1):
        visual_query = str(scene.get("visual") or row["topic_title"]).strip()
        caption = " ".join(str(scene.get("on_screen_text") or "").split()[:7])
        clip_path = work / f"clip_{index:02d}.mp4"
        attribution = _pexels_clip(visual_query, clip_path)
        if not attribution:
            attribution = _pixabay_clip(visual_query, clip_path)
        if attribution:
            source_key = attribution.get("page") or str(clip_path)
            if source_key in used_sources:
                clip_path.unlink(missing_ok=True)
                attribution = None
            else:
                used_sources.add(source_key)
        if attribution:
            clip_files.append(clip_path)
            attribution["query"] = visual_query
            attributions.append(attribution)
        else:
            clip_path.unlink(missing_ok=True)
            unmatched_scenes.append({"scene": index, "visual": visual_query})

    if unmatched_scenes:
        raise RuntimeError(
            "Render stopped: relevant, unique stock footage could not be found for every scene. "
            "No unrelated stills or repeated clips were substituted. Missing scenes: "
            + json.dumps(unmatched_scenes, ensure_ascii=False)
            + ". Configure PEXELS_API_KEY or PIXABAY_API_KEY, then retry."
        )
    if len(clip_files) < 3:
        raise RuntimeError("Render stopped: fewer than 3 unique relevant video clips were found.")

    # Match the visual timeline to the synthesized narration instead of letting
    # -shortest silently truncate the voice-over.
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                           capture_output=True, text=True, check=True)
    audio_duration = float(probe.stdout.strip())
    transition = 0.25
    shot_duration = (audio_duration + (len(clip_files) - 1) * transition) / len(clip_files)

    # Normalize all downloaded clips to identical portrait format.
    normalized = []
    for index, source in enumerate(clip_files, 1):
        target = work / f"normalized_{index:02d}.mp4"
        _run([FFMPEG_BIN, "-y", "-i", str(source), "-vf",
              f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
              f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={VIDEO_FPS},setsar=1,format=yuv420p",
              "-an", "-t", f"{shot_duration:.3f}", "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET,
              "-crf", str(VIDEO_CRF), "-pix_fmt", "yuv420p", str(target)], "Clip normalization")
        normalized.append(target)

    # Smooth crossfades replace abrupt hard cuts.
    silent_video = work / "visual_track.mp4"
    command = [FFMPEG_BIN, "-y"]
    for clip in normalized:
        command.extend(["-i", str(clip)])
    filters = []
    previous = "[0:v]"
    for index in range(1, len(normalized)):
        out = f"[xf{index}]"
        offset = index * (shot_duration - transition)
        filters.append(f"{previous}[{index}:v]xfade=transition=fade:duration={transition}:offset={offset:.3f}{out}")
        previous = out
    filters.append(f"{previous}format=yuv420p[vout]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
                    "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
                    "-pix_fmt", "yuv420p", str(silent_video)])
    _run(command, "Crossfade video assembly")

    # Local Whisper supplies word timestamps; otherwise use a conservative estimated fallback.
    alignment_path = audio_path.with_suffix(".alignment.json")
    ass_path = work / "captions.ass"
    words = []
    if alignment_path.exists():
        alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])
        token, token_start, token_end = "", None, None
        for char, begin, finish in zip(chars, starts, ends):
            if char.isspace():
                if token:
                    words.append((token, float(token_start), float(token_end)))
                    token, token_start, token_end = "", None, None
            else:
                if token_start is None:
                    token_start = begin
                token += char
                token_end = finish
        if token:
            words.append((token, float(token_start), float(token_end)))
    alignment_method = "local word alignment" if words else "estimated fallback"
    if not words:
        # Optional local forced alignment via faster-whisper. CPU int8 is suitable
        # for this 16 GB RAM / integrated-graphics target.
        try:
            from faster_whisper import WhisperModel
            whisper = WhisperModel(os.getenv("AME_WHISPER_MODEL", "base.en"),
                                   device="cpu", compute_type="int8")
            segments, _ = whisper.transcribe(str(audio_path), word_timestamps=True,
                                             vad_filter=True, beam_size=3)
            for segment in segments:
                for spoken_word in (segment.words or []):
                    if spoken_word.word.strip():
                        words.append((spoken_word.word.strip(),
                                      float(spoken_word.start), float(spoken_word.end)))
            if words:
                alignment_method = "local faster-whisper word timestamps"
        except ImportError:
            pass
        except Exception as exc:
            attributions.append({"warning": "Whisper alignment failed: " + str(exc)})
    if not words:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                               capture_output=True, text=True)
        duration = float(probe.stdout.strip() or row["duration_target_seconds"] or 45)
        tokens = narration.split()
        span = duration / max(1, len(tokens))
        words = [(word, i * span, (i + 1) * span) for i, word in enumerate(tokens)]

    def ass_time(value):
        centis = max(0, int(value * 100))
        return f"{centis // 360000}:{(centis // 6000) % 60:02}:{(centis // 100) % 60:02}.{centis % 100:02}"
    def safe_ass(value):
        return value.replace("{", "(").replace("}", ")").replace("\\", "/")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,48,&H00FFFFFF,&H0000D7FF,&HAA000000,&H64000000,-1,0,1,2,1,2,90,90,300,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    for i in range(0, len(words), 3):
        group = words[i:i+3]
        start_time, end_time = group[0][1], group[-1][2]
        karaoke = []
        for word, begin, finish in group:
            centiseconds = max(1, int((finish - begin) * 100))
            karaoke.append(f"{{\\kf{centiseconds}}}{safe_ass(word)}")
        events.append(f"Dialogue: 0,{ass_time(start_time)},{ass_time(end_time)},Default,,0,0,0,,{' '.join(karaoke)}")
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")

    output_path = work / f"ame_video_{video_id}.mp4"
    subtitle_path = ass_path.as_posix()
    vf = f"ass=filename='{subtitle_path}',format=yuv420p"
    audio_filter = "loudnorm=I=-14:TP=-1.0:LRA=7,acompressor=threshold=-18dB:ratio=2.5:attack=8:release=120,alimiter=limit=0.95"
    command = [FFMPEG_BIN, "-y", "-i", str(silent_video), "-i", str(audio_path),
               "-vf", vf, "-af", audio_filter, "-map", "0:v:0", "-map", "1:a:0", "-shortest",
               "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
               "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE, "-movflags", "+faststart", str(output_path)]
    _run(command, "Final video render")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("FFmpeg did not create the final MP4.")
    (work / "attributions.json").write_text(json.dumps(attributions, indent=2, ensure_ascii=False), encoding="utf-8")
    with get_db() as db:
        db.execute("UPDATE videos SET status='rendered',rendered_path=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (str(output_path.resolve()), video_id))
    return {
        "video_id": video_id, "status": "rendered", "rendered_path": str(output_path.resolve()),
        "resolution": f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}", "fps": VIDEO_FPS,
        "visual_style": "Unique per-scene stock video; render fails if visual matches are unavailable",
        "voice_provider": "piper-local", "visual_assets": len(clip_files),
        "unique_visual_sources": len(set(a.get("page") for a in attributions if a.get("page"))),
        "pexels_enabled": bool(PEXELS_API_KEY),
        "pixabay_enabled": bool(PIXABAY_API_KEY),
        "captions": alignment_method,
        "attribution_file": str((work / "attributions.json").resolve()),
    }
