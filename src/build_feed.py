from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sources import get_rows
from rss_generator import write_feeds


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    timezone_name = os.getenv("FEED_TIMEZONE", config.get("timezone", "America/New_York"))
    days_to_scan = int(os.getenv("DAYS_TO_SCAN", config.get("days_to_scan", 7)))
    locale = os.getenv("CRUNCHYROLL_LOCALE", config.get("locale", "en-US"))
    site_url = os.getenv("SITE_URL", "").rstrip("/")

    rows = get_rows(timezone_name, days_to_scan, locale, cr_ttl=0)
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
