import re
import feedparser
from app.config import MAX_TOPICS_PER_RUN
from app.db import get_db

FEEDS = [
 ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
 ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
 ("ScienceDaily Technology", "https://www.sciencedaily.com/rss/computers_math/technology.xml"),
 ("NASA", "https://www.nasa.gov/feed/"),
 ("The Verge", "https://www.theverge.com/rss/index.xml"),
]
TERMS = {"ai":1.0,"artificial intelligence":1.0,"robot":.9,"battery":.8,"space":.7,
 "chip":.8,"quantum":.9,"climate":.6,"medical":.7,"invention":.8,"technology":.7,
 "energy":.7,"future":.5,"breakthrough":.8,"scientist":.5}

def score(title, summary):
    text = (title + " " + summary).lower()
    relevance = min(1.0, sum(v for k,v in TERMS.items() if k in text) / 2.5)
    novelty = .65 if any(k in text for k in ("new","first","breakthrough","discovery","prototype")) else .4
    monetization = .7 if any(k in text for k in ("ai","robot","battery","chip","software","device")) else .45
    total = .5*relevance + .25*novelty + .25*monetization
    return tuple(round(x,3) for x in (relevance,novelty,monetization,total))

def discover_topics():
    processed = inserted = 0
    errors = []
    with get_db() as db:
        for source, url in FEEDS:
            if processed >= MAX_TOPICS_PER_RUN: break
            try:
                feed = feedparser.parse(url)
                if feed.bozo and not feed.entries:
                    errors.append(source + ": feed parse failed")
                    continue
                for entry in feed.entries:
                    if processed >= MAX_TOPICS_PER_RUN: break
                    title, link = (entry.get("title") or "").strip(), (entry.get("link") or "").strip()
                    summary = re.sub(r"<[^>]+>", " ", entry.get("summary","") or "")
                    summary = re.sub(r"\\s+", " ", summary).strip()[:1200]
                    if not title or not link: continue
                    r,n,m,t = score(title,summary)
                    cur = db.execute("""INSERT OR IGNORE INTO topics
                    (title,url,source_name,summary,published_at,relevance_score,novelty_score,monetization_score,total_score)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (title,link,source,summary,entry.get("published",""),r,n,m,t))
                    inserted += cur.rowcount
                    processed += 1
            except Exception as exc:
                errors.append(f"{source}: {str(exc)[:150]}")
    return {"processed":processed,"inserted":inserted,"errors":errors}

def list_topics(limit=20):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM topics ORDER BY total_score DESC, discovered_at DESC LIMIT ?",(limit,)).fetchall()]

def get_topic(topic_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM topics WHERE id=?",(topic_id,)).fetchone()
        return dict(row) if row else None
