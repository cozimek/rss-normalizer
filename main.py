from fastapi import FastAPI, Query
import requests
import feedparser
from datetime import datetime, timezone

app = FastAPI()

# Modern Chrome User-Agent (important for WordPress / Cloudflare)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT_SECONDS = 15


def iso_utc_from_struct(dt_struct):
    """Safely convert feedparser date struct to ISO 8601 UTC"""
    if not dt_struct:
        return None
    try:
        return (
            datetime.fromtimestamp(
                datetime(*dt_struct[:6], tzinfo=timezone.utc).timestamp(),
                tz=timezone.utc,
            )
            .isoformat()
        )
    except Exception:
        return None


@app.get("/")
def health():
    return {"status": "ok", "service": "rss-normalizer"}


@app.get("/feed")
def parse_feed(url: str = Query(..., description="RSS feed URL")):
    try:
        # Fetch RSS feed
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()

        # Parse RSS
        feed = feedparser.parse(resp.text)

        items = []
        for entry in feed.entries:

            # Prefer full content, fallback to summary/description
            content = None
            if "content" in entry and entry.content:
                content = entry.content[0].value
            elif "summary" in entry:
                content = entry.summary

            items.append({
                "title": entry.get("title"),
                "link": entry.get("link"),
                "author": entry.get("author"),
                "published": iso_utc_from_struct(entry.get("published_parsed")),
                "updated": iso_utc_from_struct(entry.get("updated_parsed")),
                "content": content,
                "categories": [
                    tag.term for tag in entry.get("tags", []) if hasattr(tag, "term")
                ],
            })

        return {
            "success": True,
            "feed": {
                "title": feed.feed.get("title"),
                "link": feed.feed.get("link"),
            },
            "count": len(items),
            "items": items,
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Unhandled exception",
            "details": str(e),
        }
