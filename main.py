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


def is_atom(xml_bytes: bytes) -> bool:
    """
    Fast, explicit Atom detection
    """
    head = xml_bytes[:500].lower()
    return b"<feed" in head and b"atom" in head


@app.get("/feed")
def parse_feed(url: str = Query(..., description="RSS or Atom feed URL")):
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()

        raw_xml = response.content
        atom = is_atom(raw_xml)

        feed = feedparser.parse(raw_xml)

        items = []

        # ---------------------------
        # ATOM PARSING (explicit)
        # ---------------------------
        if atom:
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
                    "author": (
                        entry.get("author")
                        or entry.get("authors", [{}])[0].get("name")
                    ),
                    "published": iso_utc(entry.get("published_parsed")),
                    "updated": iso_utc(entry.get("updated_parsed")),
                    "content": content_text,
                    "categories": [t.term for t in entry.get("tags", [])],
                }

                if item["title"] and item["link"]:
                    items.append(item)

            feed_link = None
            for l in feed.feed.get("links", []):
                if l.get("rel") == "alternate":
                    feed_link = l.get("href")

            return {
                "success": True,
                "feed": {
                    "title": feed.feed.get("title"),
                    "link": feed_link,
                },
                "count": len(items),
                "items": items,
            }

        # ---------------------------
        # RSS PARSING (existing logic)
        # ---------------------------
        for entry in feed.entries[:10]:
            raw_content = ""

            if entry.get("content"):
                raw_content = entry.content[0].value
            elif entry.get("summary"):
                raw_content = entry.summary
            elif entry.get("description"):
                raw_content = entry.description

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

            if item["title"] and item["link"]:
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
        return {
            "success": False,
            "error": "Unhandled exception",
            "details": str(e),
        }
