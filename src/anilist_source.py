"""Fallback: recently aired Crunchyroll episodes from AniList's public GraphQL API.

Used when Crunchyroll's own calendar returns nothing (e.g. Cloudflare blocks
GitHub's runners). Only shows with a Crunchyroll link on AniList are kept.
Rows use the same keys as crunchyroll_source.fetch_calendar().
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

API = "https://graphql.anilist.co"
QUERY = """
query ($page: Int, $from: Int, $to: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    airingSchedules(airingAt_greater: $from, airingAt_lesser: $to, sort: TIME_DESC) {
      airingAt
      episode
      media {
        title { romaji english }
        coverImage { large }
        externalLinks { site url }
      }
    }
  }
}
"""


def _post(variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "crunchyroll-rss/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]["Page"]


def fetch_recent(days_back: int = 7, days_ahead: int = 1, max_pages: int = 20) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(days=days_back)).timestamp())
    end = int((now + timedelta(days=days_ahead)).timestamp())
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = _post({"page": page, "from": start, "to": end})
        for s in data["airingSchedules"]:
            media = s["media"] or {}
            cr = next((l["url"] for l in media.get("externalLinks") or []
                       if (l.get("site") or "").lower() == "crunchyroll" and l.get("url")), None)
            if not cr:
                continue
            title = media["title"].get("english") or media["title"].get("romaji") or "Anime"
            ep = s["episode"]
            rows.append({
                "episode_title": f"{title} — Episode {ep}",
                "episode_number": ep,
                # '#' keeps each episode unique even though the link is the series page
                "episode_url": f"{cr}#episode-{ep}",
                "release_time": datetime.fromtimestamp(s["airingAt"], timezone.utc).isoformat(),
                "thumbnail": (media.get("coverImage") or {}).get("large") or "",
                "premium": False,
            })
        if not data["pageInfo"]["hasNextPage"]:
            break
        time.sleep(1)
    return rows
