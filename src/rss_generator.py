"""Create RSS 2.0 feeds from normalized Crunchyroll calendar entries."""
from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

CR_BASE = "https://www.crunchyroll.com/"
WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]
MEDIA_NS = "http://search.yahoo.com/mrss/"
ET.register_namespace("media", MEDIA_NS)
ATOM_NS = "http://www.w3.org/2005/Atom"
ET.register_namespace("atom", ATOM_NS)
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ET.register_namespace("content", CONTENT_NS)


def parse_release_datetime(value: str | None, tz: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(tz)
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        # Handle common date-only values from the calendar.
        parsed = datetime.combine(date.fromisoformat(raw[:10]), datetime.min.time())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def normalize_release(row: dict[str, Any], tz: ZoneInfo) -> dict[str, Any]:
    title = str(row.get("episode_title") or "Crunchyroll episode").strip()
    url = urljoin(CR_BASE, str(row.get("episode_url") or ""))
    released = parse_release_datetime(row.get("release_time"), tz)
    number = row.get("episode_number")
    thumbnail = urljoin(CR_BASE, str(row.get("thumbnail") or "")) if row.get("thumbnail") else ""
    premium = bool(row.get("premium"))
    hour = released.hour % 12 or 12
    meridiem = "AM" if released.hour < 12 else "PM"
    local_stamp = (
        f"{released.strftime('%A, %B')} {released.day}, {released.year} "
        f"at {hour}:{released.minute:02d} {meridiem} {released.tzname() or ''}"
    ).strip()
    description_parts = [f"Release: {local_stamp}"]
    if number not in (None, ""):
        description_parts.append(f"Episode number: {number}")
    if premium:
        description_parts.append("Premium")
    return {
        "title": title,
        "url": url,
        "released": released,
        "number": str(number) if number not in (None, "") else "",
        "thumbnail": thumbnail,
        "premium": premium,
        "description": " · ".join(description_parts),
        "weekday": WEEKDAYS[released.weekday()],
    }


def _feed_xml(title: str, description: str, feed_url: str,
              items: list[dict[str, Any]], site_url: str) -> bytes:
    """Plain RSS 2.0: no extra namespaces, double-quoted declaration."""
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = site_url or CR_BASE.rstrip("/")
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        datetime.now(timezone.utc), usegmt=True)

    for item in items:
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item["title"]
        link = item["url"].split("#")[0] if item["url"] else CR_BASE
        ET.SubElement(node, "link").text = link
        guid = item["url"] or f'{item["title"]}-{item["released"].isoformat()}'
        ET.SubElement(node, "guid", {"isPermaLink": "false"}).text = guid
        body = html.escape(item["description"])
        if item["thumbnail"]:
            body = f'<img src="{html.escape(item["thumbnail"])}" /><br />' + body
        ET.SubElement(node, "description").text = body
        ET.SubElement(node, "pubDate").text = format_datetime(
            item["released"].astimezone(timezone.utc), usegmt=True)
        ET.SubElement(node, "category").text = "Anime"
    body = ET.tostring(rss, encoding="unicode")
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + body).encode("utf-8")


def write_feeds(rows: list[dict[str, Any]], output_dir: Path,
                timezone_name: str, feed_title: str, feed_description: str,
                site_url: str = "") -> int:
    tz = ZoneInfo(timezone_name)
    normalized = [normalize_release(row, tz) for row in rows]
    # Stable de-duplication and chronological order.
    unique: dict[str, dict[str, Any]] = {}
    for item in normalized:
        key = item["url"] or f'{item["title"]}|{item["released"].isoformat()}'
        unique[key] = item
    now = datetime.now(timezone.utc)
    all_items = sorted(
        (x for x in unique.values() if x["released"] <= now),
        key=lambda x: x["released"], reverse=True,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = [("index.xml", feed_title, all_items)]
    targets.extend(
        (f"feeds/{day}.xml", f"{feed_title} — {day.title()}",
         [x for x in all_items if x["weekday"] == day])
        for day in WEEKDAYS
    )

    base = site_url.rstrip("/")
    for relative, title, items in targets:
        feed_url = f"{base}/{relative}" if base else ""
        xml = _feed_xml(title, feed_description, feed_url, items, base)
        path = output_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(xml)
        temporary.replace(path)


    # Human-readable page: all recent episodes, newest first, grouped by day.
    esc = html.escape
    sections, current = [], None
    for it in all_items:
        day = f"{it['released'].strftime('%A, %B')} {it['released'].day}, {it['released'].year}"
        if day != current:
            if current is not None:
                sections.append("</ul>")
            sections.append(f"<h2>{esc(day)}</h2><ul>")
            current = day
        hour = it["released"].hour % 12 or 12
        when = f"{hour}:{it['released'].minute:02d} {'AM' if it['released'].hour < 12 else 'PM'}"
        img = f'<img src="{esc(it["thumbnail"])}" alt="" loading="lazy">' if it["thumbnail"] else ""
        link = esc(it["url"].split("#")[0]) if it["url"] else CR_BASE
        sections.append(
            f'<li>{img}<div><a href="{link}">{esc(it["title"])}</a>'
            f'<span>{when}</span></div></li>')
    if current is not None:
        sections.append("</ul>")
    updated = datetime.now(tz)
    stamp_text = f"{updated.strftime('%B')} {updated.day}, {updated.year} {updated.hour % 12 or 12}:{updated.minute:02d} {'AM' if updated.hour < 12 else 'PM'} {updated.tzname() or ''}"
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>{esc(feed_title)}</title>
<link rel="alternate" type="application/rss+xml" title="{esc(feed_title)}" href="index.xml">
<style>
:root{{color-scheme:light dark}}
body{{font:16px/1.5 system-ui,sans-serif;max-width:720px;margin:0 auto;padding:20px 16px 60px}}
h1{{font-size:1.5rem;margin:.2em 0}}
h2{{font-size:1rem;margin:1.8em 0 .5em;padding-bottom:.3em;border-bottom:1px solid #8884;color:#e56a20}}
ul{{list-style:none;margin:0;padding:0}}
li{{display:flex;gap:12px;align-items:center;padding:8px 0}}
li img{{width:48px;height:68px;object-fit:cover;border-radius:6px;flex:none;background:#8883}}
li div{{display:flex;flex-direction:column}}
li a{{color:inherit;text-decoration:none;font-weight:600}}
li a:hover{{text-decoration:underline}}
li span,.meta,footer{{font-size:.85rem;opacity:.7}}
footer{{margin-top:2.5em}}
footer a{{color:#e56a20}}
</style></head><body>
<h1>{esc(feed_title)}</h1>
<p class="meta">{len(all_items)} episodes &middot; updated {esc(stamp_text)}</p>
{"".join(sections) or "<p>No episodes found.</p>"}
<footer>Feed: <a href="index.xml">RSS</a><br>
Unofficial; data from AniList and Crunchyroll's public calendar. Not affiliated with Crunchyroll.</footer>
</body></html>"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")
    return len(all_items)
