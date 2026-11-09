"""FFmpeg export profile and command builder for 9:16 short-form videos.

This module prepares a consistent export command. It does not create visuals,
voiceovers, or a complete video from a script; those pipeline stages are future work.
"""
from pathlib import Path
from app.config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_CODEC, VIDEO_CRF,
    VIDEO_PRESET, VIDEO_AUDIO_BITRATE, FFMPEG_BIN,
)

def export_profile():
    return {
        "format": "mp4",
        "orientation": "portrait",
        "width": VIDEO_WIDTH,
        "height": VIDEO_HEIGHT,
        "aspect_ratio": f"{VIDEO_WIDTH}:{VIDEO_HEIGHT}",
        "fps": VIDEO_FPS,
        "video_codec": VIDEO_CODEC,
        "crf": VIDEO_CRF,
        "preset": VIDEO_PRESET,
        "audio_codec": "aac",
        "audio_bitrate": VIDEO_AUDIO_BITRATE,
        "pixel_format": "yuv420p",
        "default_quality": "1080p" if (VIDEO_WIDTH, VIDEO_HEIGHT) == (1080, 1920) else "custom",
    }

def build_ffmpeg_command(input_path: str, output_path: str) -> list[str]:
    """Build a portrait MP4 transcode command that scales and pads without cropping."""
    source = Path(input_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,format=yuv420p"
    )
    return [
        FFMPEG_BIN, "-y", "-i", str(source),
        "-vf", vf, "-r", str(VIDEO_FPS),
        "-c:v", VIDEO_CODEC, "-preset", VIDEO_PRESET, "-crf", str(VIDEO_CRF),
        "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE,
        "-movflags", "+faststart", str(target),
    ]
