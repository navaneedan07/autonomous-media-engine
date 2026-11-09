"""Render approved scripts as a moving visual montage, not text slides.

Visuals are downloaded from the source article and Wikimedia Commons, then
animated with a slow Ken Burns zoom/pan. Short lower-third captions are used
instead of full-screen text. FFmpeg encodes the final 9:16 MP4.
"""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps
from app.config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_CODEC, VIDEO_CRF,
    VIDEO_PRESET, VIDEO_AUDIO_BITRATE, FFMPEG_BIN, VIDEO_OUTPUT_DIR,
)
from app.db import get_db
from app.services.tts import synthesize_speech


def export_profile():
    return {
        "format": "mp4", "orientation": "portrait",
        "width": VIDEO_WIDTH, "height": VIDEO_HEIGHT,
        "aspect_ratio": f"{VIDEO_WIDTH}:{VIDEO_HEIGHT}", "fps": VIDEO_FPS,
        "video_codec": VIDEO_CODEC, "crf": VIDEO_CRF, "preset": VIDEO_PRESET,
        "audio_codec": "aac", "audio_bitrate": VIDEO_AUDIO_BITRATE,
        "pixel_format": "yuv420p",
        "default_quality": "1080p" if (VIDEO_WIDTH, VIDEO_HEIGHT) == (1080, 1920) else "custom",
    }


def build_ffmpeg_command(input_path: str, output_path: str) -> list[str]:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    vf = (f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,format=yuv420p")
    return [FFMPEG_BIN, "-y", "-i", str(input_path), "-vf", vf, "-r", str(VIDEO_FPS),
            "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
            "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE, "-movflags", "+faststart", str(target)]


def _font(size, bold=False):
    candidates = (["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/Arial.ttf"] if bold
                  else ["C:/Windows/Fonts/arial.ttf"])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _download_image(url: str, path: Path) -> bool:
    try:
        response = httpx.get(url, timeout=20, follow_redirects=True,
                             headers={"User-Agent": "AutonomousMediaEngine/0.1 (personal video creator)"})
        response.raise_for_status()
        path.write_bytes(response.content)
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        path.unlink(missing_ok=True)
        return False


def _source_image(article_url: str, work: Path):
    if not article_url:
        return None
    try:
        html = httpx.get(article_url, timeout=20, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 AutonomousMediaEngine"}).text[:2_000_000]
        patterns = [
            r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""",
            r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""",
            r"""<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)""",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                url = match.group(1).replace("&amp;", "&")
                path = work / "article_source.jpg"
                if _download_image(url, path):
                    return path
    except Exception:
        pass
    return None


def _commons_image(query: str, path: Path):
    params = {
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 1400, "format": "json",
    }
    try:
        data = httpx.get("https://commons.wikimedia.org/w/api.php", params=params, timeout=25,
                         headers={"User-Agent": "AutonomousMediaEngine/0.1 (personal video creator)"}).json()
        pages = list(data.get("query", {}).get("pages", {}).values())
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if url and _download_image(url, path):
                meta = info.get("extmetadata", {})
                return path, {
                    "title": page.get("title", ""),
                    "license": (meta.get("LicenseShortName") or {}).get("value", "Check source license"),
                    "artist": (meta.get("Artist") or {}).get("value", ""),
                    "source": page.get("title", ""),
                }
    except Exception:
        pass
    return None, None


def _caption_image(source: Path, output: Path, caption: str):
    with Image.open(source) as original:
        image = ImageOps.fit(original.convert("RGB"), (VIDEO_WIDTH, VIDEO_HEIGHT),
                             method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    # Subtle lower-third only; the image remains the hero.
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, VIDEO_HEIGHT - 330, VIDEO_WIDTH, VIDEO_HEIGHT), fill=(0, 0, 0, 150))
    font = _font(48, True)
    words, lines, line = caption.split(), [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] < VIDEO_WIDTH - 120:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    y = VIDEO_HEIGHT - 255
    for line in lines[:2]:
        draw.text((60, y), line, font=font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0))
        y += 66
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    image.save(output, quality=94)


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
    # Avoid repeating the same stock image for every scene.
    article_image = _source_image(row["topic_url"], work)
    attributions, visual_paths = [], []
    for index, scene in enumerate(scenes, start=1):
        query = str(scene.get("visual") or row["topic_title"])
        image_path = work / f"visual_{index:02d}.jpg"
        license_info = None
        if article_image and index == 1:
            image_path = article_image
            license_info = {"source": row["topic_url"], "license": "Publisher source image; reuse rights must be checked"}
        else:
            image_path, license_info = _commons_image(query, image_path)
        if image_path is None or not image_path.exists():
            if article_image:
                image_path = article_image
                license_info = {"source": row["topic_url"], "license": "Publisher source image; reuse rights must be checked"}
            else:
                continue
        caption = str(scene.get("on_screen_text") or query).strip()
        caption = " ".join(caption.split()[:8])
        frame_path = work / f"frame_{index:02d}.jpg"
        _caption_image(image_path, frame_path, caption)
        visual_paths.append(frame_path)
        if license_info:
            attributions.append(license_info)

    if not visual_paths:
        raise RuntimeError("No relevant images could be retrieved. Check internet access or try another topic.")

    # Repeat retrieved visuals if fewer images than planned scenes.
    while len(visual_paths) < 3:
        visual_paths.append(visual_paths[-1])
    output_path = work / f"ame_video_{video_id}.mp4"
    # Feed each full-frame image as a timed input and animate it with a slow zoom.
    seconds = max(2.5, float(row["duration_target_seconds"] or 45) / len(visual_paths))
    command = [FFMPEG_BIN, "-y"]
    filters = []
    concat_inputs = []
    for index, path in enumerate(visual_paths):
        command.extend(["-loop", "1", "-framerate", str(VIDEO_FPS), "-t", f"{seconds:.3f}", "-i", str(path)])
        filters.append(
            f"[{index}:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},zoompan=z='min(zoom+0.0008,1.10)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
            f"s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},setsar=1,format=yuv420p[v{index}]"
        )
        concat_inputs.append(f"[v{index}]")
    filters.append("".join(concat_inputs) + f"concat=n={len(visual_paths)}:v=1:a=0[vout]")
    filter_complex = ";".join(filters)
    command.extend(["-i", str(audio_path), "-filter_complex", filter_complex,
                    "-map", "[vout]", "-map", f"{len(visual_paths)}:a:0",
                    "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
                    "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE, "-shortest",
                    "-movflags", "+faststart", str(output_path)])

    # Continuous slow zoom gives still photographs motion rather than slide transitions.
    zoom = (f"zoompan=z='min(zoom+0.0009,1.12)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},format=yuv420p")
    command = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", str(work / "visuals.txt"),
               "-i", str(audio_path), "-vf", zoom, "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET,
               "-crf", str(VIDEO_CRF), "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE,
               "-shortest", "-movflags", "+faststart", str(output_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to Windows PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg rendering timed out after 15 minutes.") from exc
    if result.returncode != 0:
        raise RuntimeError("FFmpeg render failed: " + (result.stderr[-1800:] if result.stderr else "unknown error"))
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("FFmpeg finished without creating an MP4 file.")
    (work / "attributions.json").write_text(json.dumps(attributions, indent=2, ensure_ascii=False), encoding="utf-8")

    with get_db() as db:
        db.execute("UPDATE videos SET status='rendered',rendered_path=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (str(output_path.resolve()), video_id))
    return {
        "video_id": video_id, "status": "rendered", "rendered_path": str(output_path.resolve()),
        "resolution": f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}", "fps": VIDEO_FPS,
        "visual_style": "full-frame source imagery with continuous motion and minimal lower-thirds",
        "voice": "expressive neural English voice", "visual_assets": len(visual_paths),
        "attribution_file": str((work / "attributions.json").resolve()),
        "note": "Images are not stock video footage. Check each asset's reuse license before publishing."
    }
