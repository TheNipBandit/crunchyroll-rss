"""Build feed.xml from Crunchyroll's release calendar using a headless browser.

Run: python scrape.py
Writes feed.xml, plus debug/ (page.html, page.png, links.json) so the page
structure can be inspected if extraction needs tuning.
"""
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from playwright.sync_api import sync_playwright

URL = "https://www.crunchyroll.com/releasecalendar"
ROOT = Path(__file__).parent
DEBUG = ROOT / "debug"
MAX_ITEMS = 100


def fetch_links():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            locale="en-US",
            viewport={"width": 1366, "height": 2000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector("a[href*='/watch/']", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(3000)

        DEBUG.mkdir(exist_ok=True)
        (DEBUG / "page.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(DEBUG / "page.png"), full_page=True)

        links = page.evaluate(
            """() => [...document.querySelectorAll("a[href*='/watch/']")].map(a => {
                const card = a.closest('article, li, [class*=card], [class*=item]') || a;
                return {
                    href: a.href,
                    text: (card.innerText || a.innerText || '').trim(),
                    img: (card.querySelector('img') || {}).src || ''
                };
            })"""
        )
        browser.close()
    (DEBUG / "links.json").write_text(json.dumps(links, indent=2), encoding="utf-8")
    return links


def build_items(links):
    seen, items = set(), []
    for l in links:
        href = l["href"].split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        lines = [s.strip() for s in l["text"].splitlines() if s.strip()]
        if not lines:
            continue
        title = " — ".join(lines[:3])
        items.append({"title": title, "link": href, "img": l["img"], "desc": " | ".join(lines)})
    return items[:MAX_ITEMS]


def write_feed(items):
    now = datetime.now(timezone.utc)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        "<title>Crunchyroll Release Calendar</title>",
        f"<link>{URL}</link>",
        "<description>Recently released episodes from the Crunchyroll release calendar</description>",
        f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>",
    ]
    for it in items:
        desc = escape(it["desc"])
        if it["img"]:
            desc = escape(f'<img src="{it["img"]}"/><br/>') + desc
        out += [
            "<item>",
            f"<title>{escape(it['title'])}</title>",
            f"<link>{escape(it['link'])}</link>",
            f'<guid isPermaLink="true">{escape(it["link"])}</guid>',
            f"<description>{desc}</description>",
            f"<pubDate>{format_datetime(now)}</pubDate>",
            "</item>",
        ]
    out.append("</channel></rss>")
    (ROOT / "feed.xml").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    items = build_items(fetch_links())
    print(f"{len(items)} items")
    if not items:
        print("No episodes found; see debug/ — feed left unchanged.", file=sys.stderr)
        sys.exit(1)
    write_feed(items)
