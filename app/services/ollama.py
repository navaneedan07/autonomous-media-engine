import json
import httpx
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, REQUEST_TIMEOUT_SECONDS

async def status():
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            r = await client.get(OLLAMA_BASE_URL + "/api/tags")
            r.raise_for_status()
            return {"available":True,"model_configured":OLLAMA_MODEL,
                    "models":[m.get("name") for m in r.json().get("models",[])]}
        except Exception as e:
            return {"available":False,"model_configured":OLLAMA_MODEL,"error":str(e)}

async def generate(topic, language, min_seconds, max_seconds):
    prompt = f"""
Create an original {min_seconds}-{max_seconds} second 9:16 explainer script.
Language: {language}. For bilingual output, naturally mix English and Tamil and include both.
Topic: {topic['title']}
Source URL: {topic['url']}
Publisher: {topic.get('source_name')}
Source summary: {topic.get('summary')}
Return ONLY JSON with keys:
hook (max 12 words), narration (roughly 75-100 English-equivalent words),
scene_plan (5-7 objects with time, visual, on_screen_text),
title, description, hashtags (array), fact_check_notes, sources (array).
Do not invent statistics, dates, quotes or findings. Explicitly flag claims needing verification.
Do not copy article wording. Attribute source in description.
"""
    payload = {"model":OLLAMA_MODEL,
      "messages":[{"role":"system","content":"You are a rigorous bilingual short-form science and technology documentary writer. Return valid JSON only."},
                  {"role":"user","content":prompt}],
      "stream":False,"format":"json","options":{"temperature":0.45}}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        r = await client.post(OLLAMA_BASE_URL + "/api/chat",json=payload)
        r.raise_for_status()
        data = r.json()
    result = json.loads(data["message"]["content"])
    required = ("hook","narration","scene_plan","title","description","hashtags","fact_check_notes")
    missing = [k for k in required if k not in result]
    if missing: raise ValueError("Missing generated fields: " + ", ".join(missing))
    if not isinstance(result["scene_plan"],list) or len(result["scene_plan"]) < 3:
        raise ValueError("scene_plan must contain at least 3 scenes")
    return result
