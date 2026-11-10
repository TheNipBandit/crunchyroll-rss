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


def _write_alt_feeds(output_dir: Path, title: str, description: str,
                     items: list[dict[str, Any]], base: str) -> None:
    """Atom (atom.xml) and JSON Feed (feed.json) copies of the main feed."""
    import json
    updated = items[0]["released"] if items else datetime.now(timezone.utc)
    A = "{http://www.w3.org/2005/Atom}"
    feed = ET.Element(f"{A}feed")
    ET.SubElement(feed, f"{A}title").text = title
    ET.SubElement(feed, f"{A}subtitle").text = description
    ET.SubElement(feed, f"{A}id").text = f"{base}/atom.xml" if base else CR_BASE
    ET.SubElement(feed, f"{A}updated").text = updated.isoformat()
    ET.SubElement(feed, f"{A}link", {"rel": "self", "href": f"{base}/atom.xml"})
    for it in items:
        e = ET.SubElement(feed, f"{A}entry")
        ET.SubElement(e, f"{A}title").text = it["title"]
        ET.SubElement(e, f"{A}id").text = it["url"] or f'{it["title"]}-{it["released"].isoformat()}'
        ET.SubElement(e, f"{A}link", {"href": it["url"] or CR_BASE})
        ET.SubElement(e, f"{A}updated").text = it["released"].isoformat()
        ET.SubElement(e, f"{A}published").text = it["released"].isoformat()
        ET.SubElement(e, f"{A}summary").text = it["description"]
    (output_dir / "atom.xml").write_bytes(
        ET.tostring(feed, encoding="utf-8", xml_declaration=True))
    data = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": title, "description": description,
        "home_page_url": base or CR_BASE,
        "feed_url": f"{base}/feed.json" if base else "",
        "items": [{
            "id": it["url"] or f'{it["title"]}-{it["released"].isoformat()}',
            "url": it["url"] or CR_BASE,
            "title": it["title"],
            "content_text": it["description"],
            "date_published": it["released"].isoformat(),
            **({"image": it["thumbnail"]} if it["thumbnail"] else {}),
        } for it in items],
    }
    (output_dir / "feed.json").write_text(json.dumps(data, indent=1), encoding="utf-8")


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

    _write_alt_feeds(output_dir, feed_title, feed_description, all_items, base)

    # Tiny human-readable landing page.
    links = ['<li><a href="index.xml">All releases (RSS)</a></li>',
             '<li><a href="atom.xml">All releases (Atom)</a></li>',
             '<li><a href="feed.json">All releases (JSON Feed)</a></li>']
    links.extend(f'<li><a href="feeds/{d}.xml">{d.title()}</a></li>' for d in WEEKDAYS)
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crunchyroll RSS</title>
<link rel="alternate" type="application/rss+xml" title="Crunchyroll Episode Releases" href="index.xml">
<link rel="alternate" type="application/atom+xml" title="Crunchyroll Episode Releases (Atom)" href="atom.xml">
<style>
body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.6}
a{color:#e56a20}code{overflow-wrap:anywhere}
</style></head><body><h1>Crunchyroll RSS</h1>
<p>Subscribe to the main feed or an individual weekday feed in your RSS reader.</p>
<ul>""" + "".join(links) + """</ul>
<p>Feeds are generated automatically from Crunchyroll's public release calendar.
Unofficial project; not affiliated with Crunchyroll.</p></body></html>"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")
    return len(all_items)
