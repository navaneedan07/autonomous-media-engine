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
Language: English only. Use short, natural spoken sentences with commas and full stops to create audible pauses.
Topic: {topic['title']}
Source URL: {topic['url']}
Publisher: {topic.get('source_name')}
Source summary: {topic.get('summary')}
Return ONLY JSON with keys:
hook (max 12 words), narration (roughly 65-80 words for a 30-40 second voice-over at a calm 125-140 words per minute),
scene_plan (5-7 objects with time, visual, on_screen_text). Each visual must describe one concrete, filmable subject/action directly illustrating that exact narration beat; use short stock-footage search phrases, not abstract concepts, metaphors, generic technology graphics, or unrelated B-roll. Keep scene order aligned to narration order. Never introduce an object, activity, industry, product, or setting absent from the narration. If a beat has no honest stock-footage representation, describe the closest literal real-world action rather than inventing a scene. on_screen_text must be a short readable phrase (max 5 words), never timestamps or narration paragraphs.
title, description, hashtags (array), fact_check_notes, sources (array).
Do not invent statistics, dates, quotes or findings. Explicitly flag claims needing verification.
Do not copy article wording. Attribute source in description.
"""
    payload = {"model":OLLAMA_MODEL,
      "messages":[{"role":"system","content":"You are a rigorous English-only short-form science and technology documentary writer and factual visual planner. Never invent illustrative scenes. Return valid JSON only."},
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
