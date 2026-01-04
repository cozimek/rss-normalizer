from fastapi import FastAPI, Query
import feedparser
import requests

app = FastAPI()

@app.get("/feed")
def normalize_feed(url: str = Query(...)):
    try:
        # Fetch RSS explicitly (don’t let feedparser fetch silently)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        feed = feedparser.parse(resp.content)

        if feed.bozo:
            return {
                "success": False,
                "error": "Feed parsing error",
                "details": str(feed.bozo_exception)
            }

        items = []
        for entry in feed.entries:
            items.append({
                "title": entry.get("title"),
                "link": entry.get("link"),
                "author": entry.get("author"),
                "published": entry.get("published"),
                "summary": entry.get("summary"),
                "content": (
                    entry.content[0].value
                    if hasattr(entry, "content") and entry.content
                    else entry.get("summary")
                ),
                "categories": [t.term for t in entry.get("tags", [])]
            })

        return {
            "success": True,
            "feed_title": feed.feed.get("title"),
            "item_count": len(items),
            "items": items
        }

    except Exception as e:
        # NEVER crash — always return JSON
        return {
            "success": False,
            "error": "Unhandled exception",
            "details": str(e)
        }
