import json
from app.db import get_db
from app.config import CONTENT_LANGUAGE, VIDEO_MIN_SECONDS, VIDEO_MAX_SECONDS, OLLAMA_MODEL
from app.services.research import get_topic
from app.services.ollama import generate

def get_video(video_id):
    with get_db() as db:
        row = db.execute("""SELECT v.*,t.title AS topic_title,s.language,s.hook,s.narration,
        s.scene_plan,s.title AS video_title,s.description,s.hashtags,s.fact_check_notes,s.model_name
        FROM videos v JOIN topics t ON t.id=v.topic_id JOIN scripts s ON s.id=v.script_id
        WHERE v.id=?""",(video_id,)).fetchone()
        return dict(row) if row else None

async def create_draft(topic_id):
    topic = get_topic(topic_id)
    if not topic: raise ValueError("Topic not found")
    data = await generate(topic,CONTENT_LANGUAGE,VIDEO_MIN_SECONDS,VIDEO_MAX_SECONDS)
    with get_db() as db:
        cur = db.execute("""INSERT INTO scripts
        (topic_id,language,hook,narration,scene_plan,title,description,hashtags,fact_check_notes,model_name)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (topic_id,CONTENT_LANGUAGE,data["hook"],data["narration"],
         json.dumps(data["scene_plan"],ensure_ascii=False),data["title"],data["description"],
         json.dumps(data["hashtags"],ensure_ascii=False),data["fact_check_notes"],OLLAMA_MODEL))
        script_id = cur.lastrowid
        cur = db.execute("INSERT INTO videos(topic_id,script_id,duration_target_seconds,status) VALUES (?,?,?,'draft')",
                         (topic_id,script_id,VIDEO_MAX_SECONDS))
        video_id = cur.lastrowid
        db.execute("UPDATE topics SET status='scripted' WHERE id=?",(topic_id,))
    return get_video(video_id)

def list_videos(limit=30):
    with get_db() as db:
        return [dict(r) for r in db.execute("""SELECT v.id,v.status,v.duration_target_seconds,v.created_at,
        t.title AS topic_title,s.title AS video_title,s.language FROM videos v
        JOIN topics t ON t.id=v.topic_id JOIN scripts s ON s.id=v.script_id
        ORDER BY v.created_at DESC LIMIT ?""",(limit,)).fetchall()]

def decide(video_id, decision, reason=""):
    if decision not in ("approved","rejected"): raise ValueError("Invalid decision")
    with get_db() as db:
        if not db.execute("SELECT id FROM videos WHERE id=?",(video_id,)).fetchone():
            raise ValueError("Video not found")
        db.execute("INSERT INTO approvals(video_id,decision,reason) VALUES (?,?,?)",(video_id,decision,reason))
        db.execute("UPDATE videos SET status=?,approval_reason=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (decision,reason,video_id))
    return get_video(video_id)
