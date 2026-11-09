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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
CONTENT_LANGUAGE = os.getenv("CONTENT_LANGUAGE", "bilingual")
VIDEO_MIN_SECONDS = int(os.getenv("VIDEO_MIN_SECONDS", "30"))
VIDEO_MAX_SECONDS = int(os.getenv("VIDEO_MAX_SECONDS", "45"))
MAX_TOPICS_PER_RUN = int(os.getenv("MAX_TOPICS_PER_RUN", "40"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
