from fastapi import FastAPI, HTTPException, Query
import feedparser
from datetime import timezone
from typing import List
import requests

app = FastAPI(title="RSS Normalizer", version="1.0")


def iso_utc(dt_struct):
    if not dt_struct:
        return None
    return (
        feedparser._mktime_tz(dt_struct)
        and
        __import__("datetime")
        .datetime
        .fromtimestamp(feedparser._mktime_tz(dt_struct), tz=timezone.utc)
        .isoformat()
    )


@app.get("/feed")
def parse_feed(url: str = Query(..., description="RSS or Atom feed URL")):
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if feed.bozo and not feed.entries:
        raise HTTPException(status_code=502, detail="Invalid or unreadable feed")

    items = []

    for entry in feed.entries:
        title = entry.get("title")
        link = entry.get("link")

        if not title or not link:
            continue

        author = (
            entry.get("author")
            or entry.get("dc_creator")
            or "Unknown"
        )

        published = (
            iso_utc(entry.get("published_parsed"))
            or iso_utc(entry.get("updated_parsed"))
        )

        summary_html = entry.get("summary", "")
        content_html = ""

        if "content" in entry and len(entry.content) > 0:
            content_html = entry.content[0].get("value", "")

        if not content_html:
            content_html = summary_html

        categories = []
        for tag in entry.get("tags", []):
            term = tag.get("term")
            if term:
                categories.append(term)

        items.append({
            "title": title,
            "url": link,
            "author": author,
            "published_at": published,
            "summary_html": summary_html,
            "content_html": content_html,
            "categories": categories
        })

    return {
        "feed_url": url,
        "fetched_at": __import__("datetime").datetime.now(tz=timezone.utc).isoformat(),
        "items": items
    }
