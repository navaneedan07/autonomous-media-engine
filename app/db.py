import sqlite3
from pathlib import Path
from contextlib import contextmanager
from app.config import DATABASE_PATH

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS topics (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
 source_name TEXT, summary TEXT, published_at TEXT, discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
 relevance_score REAL DEFAULT 0, novelty_score REAL DEFAULT 0, monetization_score REAL DEFAULT 0,
 total_score REAL DEFAULT 0, status TEXT DEFAULT 'new'
);
CREATE TABLE IF NOT EXISTS research_sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL, url TEXT NOT NULL,
 title TEXT, source_name TEXT, excerpt TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS scripts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL, language TEXT DEFAULT 'bilingual',
 hook TEXT, narration TEXT NOT NULL, scene_plan TEXT NOT NULL, title TEXT, description TEXT,
 hashtags TEXT, fact_check_notes TEXT, model_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS videos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL, script_id INTEGER NOT NULL,
 status TEXT DEFAULT 'draft', duration_target_seconds INTEGER DEFAULT 45, rendered_path TEXT,
 approval_reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(topic_id) REFERENCES topics(id), FOREIGN KEY(script_id) REFERENCES scripts(id)
);
CREATE TABLE IF NOT EXISTS approvals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL,
 decision TEXT CHECK(decision IN ('approved','rejected')), reason TEXT,
 decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS publications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, platform TEXT NOT NULL,
 platform_post_id TEXT, status TEXT DEFAULT 'not_configured', published_at TEXT,
 UNIQUE(video_id, platform), FOREIGN KEY(video_id) REFERENCES videos(id)
);
CREATE TABLE IF NOT EXISTS analytics (
 id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL, platform TEXT NOT NULL,
 views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0, shares INTEGER DEFAULT 0,
 watch_time_seconds REAL DEFAULT 0, captured_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(video_id) REFERENCES videos(id)
);
CREATE INDEX IF NOT EXISTS idx_topics_score ON topics(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
"""

def init_db():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as db:
        db.executescript(SCHEMA)

@contextmanager
def get_db():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()
