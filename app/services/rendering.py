"""Render approved scripts into vertical Shorts using real stock video clips.

Pexels is the preferred video source (free API key required). Wikimedia/article
images remain a clearly identified fallback. FFmpeg handles clip cuts, motion,
voice-over, captions, and final encoding.
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

PEXELS_API_KEY = __import__("os").getenv("PEXELS_API_KEY", "").strip()


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
    if not PEXELS_API_KEY:
        return None
    try:
        response = httpx.get(
            "https://api.pexels.com/videos/search",
            params={"query": query, "per_page": 8, "orientation": "portrait"},
            headers={"Authorization": PEXELS_API_KEY}, timeout=30,
        )
        response.raise_for_status()
        videos = response.json().get("videos", [])
        # Prefer vertical HD files; never download 4K for this local 16 GB machine.
        candidates = []
        for video in videos:
            for item in video.get("video_files", []):
                width, height = item.get("width") or 0, item.get("height") or 0
                if item.get("link") and height >= width and width >= 720:
                    candidates.append((width * height, item["link"], video.get("url", "")))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[0] > 1920 * 1080, x[0]))
        _, url, page = candidates[0]
        with httpx.stream("GET", url, timeout=90, follow_redirects=True) as stream:
            stream.raise_for_status()
            with destination.open("wb") as f:
                for chunk in stream.iter_bytes(1024 * 1024):
                    f.write(chunk)
        if destination.exists() and destination.stat().st_size > 100_000:
            return {"provider": "Pexels", "page": page, "license": "Pexels license; review terms before publication"}
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
    audio_path = work / "narration.mp3"
    synthesize_speech(narration, str(audio_path))
    try:
        scenes = json.loads(row["scene_plan"] or "[]")
    except json.JSONDecodeError:
        scenes = []
    if not isinstance(scenes, list) or not scenes:
        scenes = [{"visual": row["topic_title"], "on_screen_text": row["topic_title"]}]
    scenes = scenes[:10]
    article_image = _article_image(row["topic_url"], work)
    clip_files, attributions = [], []
    fallback_image = article_image

    for index, scene in enumerate(scenes, 1):
        visual_query = str(scene.get("visual") or row["topic_title"]).strip()
        caption = " ".join(str(scene.get("on_screen_text") or "").split()[:7])
        clip_path = work / f"clip_{index:02d}.mp4"
        attribution = _pexels_clip(visual_query, clip_path)
        if attribution:
            clip_files.append(clip_path)
            attribution["query"] = visual_query
            attributions.append(attribution)
            continue

        # No stock-video key or no matching clip: use a licensed/reference still,
        # but do not pretend it is footage.
        image_path, image_credit = _commons_image(visual_query, work / f"still_{index:02d}.jpg")
        if image_path is None:
            image_path = fallback_image
        if image_path is None:
            continue
        if image_credit:
            attributions.append(image_credit)
        elif image_path == fallback_image:
            attributions.append({"provider": "Publisher article image", "source": row["topic_url"],
                                 "license": "Reuse rights must be checked"})
        card = work / f"visual_{index:02d}.jpg"
        _caption_card(image_path, card, caption or row["topic_title"])
        # Turn still into a short motion clip. Real stock footage remains the preferred path.
        _run([FFMPEG_BIN, "-y", "-loop", "1", "-i", str(card), "-t",
              str(max(3, int(row["duration_target_seconds"] or 45) // max(1, len(scenes)))),
              "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                     f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},zoompan=z='min(zoom+0.001,1.12)':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},format=yuv420p",
              "-an", "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
              str(clip_path)], "Still-image motion clip")
        clip_files.append(clip_path)

    if not clip_files:
        raise RuntimeError("No usable video clips or images found. Add a Pexels API key or check internet access.")

    # Normalize all downloaded clips to identical portrait format, then concatenate.
    normalized = []
    for index, source in enumerate(clip_files, 1):
        target = work / f"normalized_{index:02d}.mp4"
        _run([FFMPEG_BIN, "-y", "-i", str(source), "-vf",
              f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
              f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={VIDEO_FPS},setsar=1,format=yuv420p",
              "-an", "-t", "8", "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET,
              "-crf", str(VIDEO_CRF), "-pix_fmt", "yuv420p", str(target)], "Clip normalization")
        normalized.append(target)

    concat_file = work / "clips.txt"
    concat_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in normalized), encoding="utf-8")
    silent_video = work / "visual_track.mp4"
    _run([FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
          "-c", "copy", str(silent_video)], "Clip concatenation")

    # Sentence-level captions, timed approximately across the narration.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration) if s.strip()]
    caption_file = work / "captions.srt"
    try:
        import wave
        with wave.open(str(audio_path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
    except Exception:
        duration = float(row["duration_target_seconds"] or 45)
    total_words = max(1, sum(len(s.split()) for s in sentences))
    cursor, srt = 0.0, []
    for sentence in sentences:
        span = duration * len(sentence.split()) / total_words
        start, end = cursor, min(duration, cursor + span)
        def stamp(value):
            ms = int(value * 1000)
            return f"{ms//3600000:02}:{(ms//60000)%60:02}:{(ms//1000)%60:02},{ms%1000:03}"
        srt.extend([str(len(srt)//4+1), f"{stamp(start)} --> {stamp(end)}", sentence, ""])
        cursor = end
    caption_file.write_text("\n".join(srt), encoding="utf-8")

    output_path = work / f"ame_video_{video_id}.mp4"
    # Subtitles are burned in using FFmpeg's subtitles filter. The narration is foreground audio.
    subtitle_path = str(caption_file.resolve()).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=170',format=yuv420p"
    command = [FFMPEG_BIN, "-y", "-i", str(silent_video), "-i", str(audio_path),
               "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-shortest",
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
        "visual_style": "Pexels stock video montage when API key is configured; otherwise moving stills",
        "voice": "expressive neural English voice", "visual_assets": len(clip_files),
        "pexels_enabled": bool(PEXELS_API_KEY),
        "captions": "sentence-timed burned-in subtitles",
        "attribution_file": str((work / "attributions.json").resolve()),
    }
