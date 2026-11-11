"""Combine Crunchyroll's own calendar with AniList's airing schedule.

Crunchyroll's calendar is the primary source (it includes dubs and catalog
batch releases). AniList fills in anything Crunchyroll's calendar misses, and
is the only source if Crunchyroll blocks us or the optional crunchyroll-api
package is not installed.
"""
from __future__ import annotations

import re
import time
from typing import Any

from anilist_source import fetch_recent

try:
    from crunchyroll_source import fetch_calendar
except Exception as exc:  # package missing/unusable: AniList only
    fetch_calendar = None
    print(f"Crunchyroll calendar disabled: {type(exc).__name__}: {exc}", flush=True)

_cr_cache: dict[str, Any] = {"at": 0.0, "rows": []}


def _key(title: Any, number: Any) -> str:
    t = re.sub(r"\s+[\u2014-]\s+Episode\s+\S+$", "", str(title or ""), flags=re.I)
    t = re.sub(r"[^a-z0-9]+", "", t.lower())
    nums = re.findall(r"\d+", str(number or ""))
    return f"{t}|{'-'.join(nums)}"


def get_rows(timezone_name: str, days_back: int, locale: str = "en-US",
             cr_ttl: int = 600) -> list[dict[str, Any]]:
    """Return merged release rows. Crunchyroll is re-queried at most every
    `cr_ttl` seconds (the last good result is kept if a query fails)."""
    cr: list[dict[str, Any]] = []
    if fetch_calendar is not None:
        if time.time() - _cr_cache["at"] >= cr_ttl:
            try:
                rows = fetch_calendar(timezone_name, days_back=days_back,
                                      days_ahead=0, locale=locale)
                _cr_cache["rows"] = rows
                print(f"Crunchyroll calendar: {len(rows)} releases", flush=True)
                for r in rows[:2]:
                    print(f"  sample: {r}", flush=True)
            except Exception as exc:
                print(f"Crunchyroll calendar failed: {type(exc).__name__}: {exc}", flush=True)
            _cr_cache["at"] = time.time()
        cr = _cr_cache["rows"]

    try:
        al = fetch_recent(days_back=days_back)
    except Exception as exc:
        print(f"AniList failed: {type(exc).__name__}: {exc}", flush=True)
        al = []

    seen = {_key(r.get("episode_title"), r.get("episode_number")) for r in cr}
    extra = [r for r in al if _key(r.get("episode_title"), r.get("episode_number")) not in seen]
    print(f"sources: crunchyroll={len(cr)} anilist={len(al)} anilist_added={len(extra)}", flush=True)
    return list(cr) + extra
