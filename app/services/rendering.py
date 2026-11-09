"""Render approved scripts into vertical MP4 motion-graphic videos.

The first renderer uses locally generated text scene cards and Windows SAPI TTS.
It intentionally does not claim to generate photorealistic footage.
"""
import json
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
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
    source, target = Path(input_path), Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    vf = (f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
          f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p")
    return [FFMPEG_BIN, "-y", "-i", str(source), "-vf", vf, "-r", str(VIDEO_FPS),
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


def _wrap(draw, text, font, max_width):
    words, lines, line = str(text).split(), [], ""
    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _make_scene_card(path, title, caption, index, count):
    image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), (10, 18, 34))
    draw = ImageDraw.Draw(image)
    # Simple branded gradient-like bands, generated locally.
    for y in range(VIDEO_HEIGHT):
        shade = int(18 + 24 * y / VIDEO_HEIGHT)
        draw.line((0, y, VIDEO_WIDTH, y), fill=(8, shade, min(70, shade + 25)))
    draw.rounded_rectangle((70, 120, VIDEO_WIDTH - 70, 132), radius=6, fill=(65, 190, 255))
    draw.text((80, 175), "AUTONOMOUS MEDIA ENGINE", font=_font(30, True), fill=(120, 205, 255))
    draw.text((80, 270), f"SCENE {index:02d} / {count:02d}", font=_font(28, True), fill=(170, 185, 205))
    y = 520
    for line in _wrap(draw, title, _font(66, True), VIDEO_WIDTH - 160):
        draw.text((80, y), line, font=_font(66, True), fill=(255, 255, 255))
        y += 88
    y += 75
    for line in _wrap(draw, caption, _font(42), VIDEO_WIDTH - 160):
        draw.text((80, y), line, font=_font(42), fill=(195, 215, 235))
        y += 62
    draw.text((80, VIDEO_HEIGHT - 150), "FOLLOW FOR MORE EXPLAINERS", font=_font(28, True), fill=(115, 195, 255))
    image.save(path, quality=95)


def render_approved_video(video_id: int) -> dict:
    with get_db() as db:
        row = db.execute("""SELECT v.id,v.status,v.duration_target_seconds,s.narration,
            s.scene_plan,s.title FROM videos v JOIN scripts s ON s.id=v.script_id WHERE v.id=?""",
            (video_id,)).fetchone()
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
        scenes = [{"visual": row["title"] or "Today's technology explained",
                   "on_screen_text": row["title"] or "Technology explained"}]

    # Read actual WAV duration so the scene cards cover the narration.
    import wave
    with wave.open(str(audio_path), "rb") as wav:
        audio_seconds = wav.getnframes() / float(wav.getframerate())
    per_scene = max(1.0, audio_seconds / len(scenes))
    concat_path = work / "scenes.txt"
    with concat_path.open("w", encoding="utf-8") as manifest:
        for index, scene in enumerate(scenes, start=1):
            frame = work / f"scene_{index:02d}.png"
            heading = scene.get("on_screen_text") or scene.get("visual") or f"Scene {index}"
            caption = scene.get("visual") or ""
            _make_scene_card(frame, row["title"] or "Today's story", heading + "\n" + caption, index, len(scenes))
            safe_path = str(frame.resolve()).replace("\\", "/").replace("'", "'\\''")
            manifest.write(f"file '{safe_path}'\n")
            manifest.write(f"duration {per_scene:.3f}\n")
        last = work / f"scene_{len(scenes):02d}.png"
        safe_last = str(last.resolve()).replace("\\", "/").replace("'", "'\\''")
        manifest.write(f"file '{safe_last}'\n")

    output_path = work / f"ame_video_{video_id}.mp4"
    command = [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path),
               "-i", str(audio_path), "-vf", f"fps={VIDEO_FPS},format=yuv420p",
               "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
               "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE, "-shortest",
               "-movflags", "+faststart", str(output_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to Windows PATH, or set FFMPEG_BIN in .env.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FFmpeg rendering timed out after 15 minutes.") from exc
    if result.returncode != 0:
        raise RuntimeError("FFmpeg render failed: " + (result.stderr[-1800:] if result.stderr else "unknown error"))
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("FFmpeg finished without creating an MP4 file.")

    with get_db() as db:
        db.execute("UPDATE videos SET status='rendered',rendered_path=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (str(output_path.resolve()), video_id))
    return {"video_id": video_id, "status": "rendered", "rendered_path": str(output_path.resolve()),
            "duration_seconds": round(audio_seconds, 2), "resolution": f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
            "visual_style": "locally generated motion-graphic scene cards", "audio": "offline Windows SAPI voice"}
