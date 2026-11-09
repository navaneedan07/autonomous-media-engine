import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
APP_NAME = os.getenv("APP_NAME", "Autonomous Media Engine")
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "content.db"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
CONTENT_LANGUAGE = os.getenv("CONTENT_LANGUAGE", "english")
VIDEO_MIN_SECONDS = int(os.getenv("VIDEO_MIN_SECONDS", "30"))
VIDEO_MAX_SECONDS = int(os.getenv("VIDEO_MAX_SECONDS", "45"))
MAX_TOPICS_PER_RUN = int(os.getenv("MAX_TOPICS_PER_RUN", "40"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "180"))
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_CODEC = os.getenv("VIDEO_CODEC", "libx264")
VIDEO_CRF = int(os.getenv("VIDEO_CRF", "20"))
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")
VIDEO_AUDIO_BITRATE = os.getenv("VIDEO_AUDIO_BITRATE", "192k")
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
VIDEO_OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", str(BASE_DIR / "output")))
