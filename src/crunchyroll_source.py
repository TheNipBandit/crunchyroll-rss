"""Fetch release-calendar entries using the community crunchyroll-api package."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from crunchyroll_api import CrunchyrollClient


def fetch_calendar(timezone_name: str = "America/New_York",
                   days_back: int = 7,
                   days_ahead: int = 0,
                   locale: str = "en-US") -> list[dict[str, Any]]:
    """Fetch and de-duplicate the calendar from `days_back` days ago through
    `days_ahead` days from now (today is always included).

    Crunchyroll's calendar is unofficial/undocumented and best-effort. The
    upstream library scrapes its public HTML schema.org blocks. No login or
    account credentials are used.
    """
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    client = CrunchyrollClient(locale=locale)
    releases: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    try:
        for offset in range(-max(0, days_back), max(0, days_ahead) + 1):
            query_date = (today + timedelta(days=offset)).isoformat()
            try:
                # premium_only=False means don't restrict the page to Premium
                # releases; the feed includes every release exposed publicly.
                rows = client.get_release_calendar(
                    date=query_date, premium_only=False
                )
                for row in rows:
                    url = row.get("episode_url") or ""
                    release_time = row.get("release_time") or ""
                    title = row.get("episode_title") or "Crunchyroll episode"
                    key = url or f"{title}|{release_time}|{row.get('episode_number', '')}"
                    if key not in releases:
                        releases[key] = dict(row)
            except Exception as exc:  # keep other dates usable if one request fails
                errors.append(f"{query_date}: {type(exc).__name__}: {exc}")
    finally:
        try:
            client.http.close()
        except Exception:
            pass

    if not releases and errors:
        raise RuntimeError(
            "Every Crunchyroll calendar request failed. " + " | ".join(errors)
        )
    if errors:
        print("Some calendar dates could not be fetched: " + " | ".join(errors))
    return list(releases.values())
