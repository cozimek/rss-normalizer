from fastapi import FastAPI, Query
import feedparser
import requests
from bs4 import BeautifulSoup
import html
from datetime import datetime, timezone

app = FastAPI()

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml,application/xml,text/xml,*/*",
}


def log(msg: str):
    print(f"[RSS-NORMALIZER] {msg}")


def html_to_text(raw_html: str) -> str:
    if not raw_html:
        return ""

    decoded = html.unescape(raw_html)
    soup = BeautifulSoup(decoded, "lxml")

    for tag in soup(["script", "style", "noscript", "iframe", "img"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)

    return cleaned.strip()


def iso_utc(dt_struct):
    if not dt_struct:
        return None
    return datetime(*dt_struct[:6], tzinfo=timezone.utc).isoformat()


# -------------------------
# 🔥 KEEPALIVE ENDPOINT
# -------------------------
@app.get("/ping")
def ping():
    return {
        "status": "ok",
        "service": "rss-normalizer",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# -------------------------
# RSS / ATOM NORMALIZER
# -------------------------
@app.get("/feed")
def parse_feed(url: str = Query(..., description="RSS or Atom feed URL")):
    try:
        log(f"Fetching URL: {url}")

        response = requests.get(url, headers=HEADERS, timeout=20)
        log(f"HTTP status: {response.status_code}")
        log(f"Content-Type: {response.headers.get('Content-Type')}")
        log(f"Response length: {len(response.content)} bytes")
        log(f"First 1000 chars of response:\n{response.text[:1000]}")

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        log(f"Feedparser version: {feedparser.__version__}")
        log(f"Feed bozo: {feed.bozo}")

        if feed.bozo and hasattr(feed, "bozo_exception"):
            log(f"Bozo exception: {feed.bozo_exception}")

        log(f"Feed keys: {list(feed.feed.keys())}")
        log(f"Entry count: {len(feed.entries)}")

        items = []

        for entry in feed.entries[:10]:
            raw_content = ""

            if entry.get("content"):
                raw_content = entry.content[0].value
            elif entry.get("summary"):
                raw_content = entry.summary

            content_text = html_to_text(raw_content)

            item = {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "author": entry.get("author"),
                "published": iso_utc(entry.get("published_parsed")),
                "updated": iso_utc(entry.get("updated_parsed")),
                "content": content_text,
                "categories": [t.term for t in entry.get("tags", [])],
            }

            items.append(item)

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
        log(f"Unhandled exception: {str(e)}")
        return {
            "success": False,
            "error": "Unhandled exception",
            "details": str(e),
        }
