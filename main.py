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
    "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*",
}


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


def extract_feed_link(feed):
    """
    Works for both RSS and Atom feeds
    """
    if feed.feed.get("link"):
        return feed.feed.get("link")

    links = feed.feed.get("links", [])
    for l in links:
        if l.get("rel") == "alternate" and l.get("href"):
            return l.get("href")

    return None


def extract_entry_content(entry):
    """
    Defensive extraction that supports RSS + Atom
    """
    if entry.get("content"):
        return entry.content[0].value

    if entry.get("summary"):
        return entry.summary

    if entry.get("description"):
        return entry.description

    return ""


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/feed")
def parse_feed(url: str = Query(..., description="RSS or Atom feed URL")):
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        items = []

        for entry in feed.entries[:10]:
            raw_content = extract_entry_content(entry)
            content_text = html_to_text(raw_content)

            # Do NOT drop valid entries just because content is short
            item = {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "author": entry.get("author"),
                "published": iso_utc(entry.get("published_parsed")),
                "updated": iso_utc(entry.get("updated_parsed")),
                "content": content_text,
                "categories": [t.term for t in entry.get("tags", [])],
            }

            # Require at least title + link to include
            if item["title"] and item["link"]:
                items.append(item)

        return {
            "success": True,
            "feed": {
                "title": feed.feed.get("title"),
                "link": extract_feed_link(feed),
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
