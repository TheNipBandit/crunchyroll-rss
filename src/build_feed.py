from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anilist_source import fetch_recent
from crunchyroll_source import fetch_calendar
from rss_generator import write_feeds


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    timezone_name = os.getenv("FEED_TIMEZONE", config.get("timezone", "America/New_York"))
    days_to_scan = int(os.getenv("DAYS_TO_SCAN", config.get("days_to_scan", 7)))
    locale = os.getenv("CRUNCHYROLL_LOCALE", config.get("locale", "en-US"))
    site_url = os.getenv("SITE_URL", "").rstrip("/")

    print(f"Fetching Crunchyroll releases for the next {days_to_scan} calendar days...")
    try:
        rows = fetch_calendar(timezone_name, days_to_scan, locale)
    except Exception as exc:
        print(f"Crunchyroll calendar failed: {type(exc).__name__}: {exc}")
        rows = []
    if not rows:
        print("Crunchyroll calendar returned 0 releases; using AniList fallback.")
        rows = fetch_recent(days_back=days_to_scan)
        print(f"AniList fallback found {len(rows)} Crunchyroll releases.")
    if not rows:
        sys.exit("No releases found from any source; leaving the published feed unchanged.")
    count = write_feeds(
        rows=rows,
        output_dir=ROOT / "docs",
        timezone_name=timezone_name,
        feed_title=config.get("feed_title", "Crunchyroll Episode Releases"),
        feed_description=config.get(
            "feed_description",
            "All releases listed in Crunchyroll's public release calendar."
        ),
        site_url=site_url,
    )
    print(f"Generated RSS feeds with {count} unique release entries.")


if __name__ == "__main__":
    main()
