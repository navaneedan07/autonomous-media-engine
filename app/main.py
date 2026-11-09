from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.config import APP_NAME
from app.services.rendering import export_profile, render_approved_video
from app.db import init_db
from app.services.research import discover_topics,list_topics
from app.services.ollama import status as ollama_status
from app.services.content import create_draft,get_video,list_videos,decide

app = FastAPI(title=APP_NAME,version="0.1.0",description="Local-first AI content research and approval API.")

@app.on_event("startup")
def startup(): init_db()

class Decision(BaseModel):
    reason: str = Field(default="",max_length=1000)

@app.get("/")
def root(): return {"name":APP_NAME,"status":"running","docs":"/docs"}

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/videos/{video_id}/render")
def render_video(video_id:int):
    try: return render_approved_video(video_id)
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception as e: raise HTTPException(500,"Rendering failed: "+str(e))

@app.get("/render/settings")
def render_settings():
    """Return the configured vertical video export profile; does not render a video."""
    return export_profile()

@app.get("/ollama/status")
async def ollama(): return await ollama_status()

@app.post("/research/discover")
def discover(): return discover_topics()

@app.get("/topics")
def topics(limit:int=20): return list_topics(max(1,min(limit,100)))

@app.post("/videos/generate/{topic_id}")
async def generate(topic_id:int):
    try: return await create_draft(topic_id)
    except ValueError as e: raise HTTPException(404,str(e))
    except Exception as e: raise HTTPException(502,"Generation failed: "+str(e))

@app.get("/videos")
def videos(limit:int=30): return list_videos(max(1,min(limit,100)))

@app.get("/videos/{video_id}")
def video(video_id:int):
    result=get_video(video_id)
    if not result: raise HTTPException(404,"Video not found")
    return result

@app.post("/videos/{video_id}/approve")
def approve(video_id:int,body:Decision=Decision()):
    try: return decide(video_id,"approved",body.reason)
    except ValueError as e: raise HTTPException(404,str(e))

@app.post("/videos/{video_id}/reject")
def reject(video_id:int,body:Decision):
    try: return decide(video_id,"rejected",body.reason)
    except ValueError as e: raise HTTPException(404,str(e))
