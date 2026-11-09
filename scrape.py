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
NET = []


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
        NET.clear()

        def on_response(r):
            try:
                if "crunchyroll" not in r.url:
                    return
                ct = r.headers.get("content-type", "")
                rec = {"url": r.url, "status": r.status, "type": ct}
                if "json" in ct and r.status == 200:
                    rec["body"] = r.json()
                NET.append(rec)
            except Exception:
                pass

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.click("text=OK", timeout=5000)
        except Exception:
            pass
        try:
            page.wait_for_selector("a[href*='/watch/']", timeout=60000)
        except Exception:
            pass
        page.wait_for_timeout(5000)

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
    summary = [{k: v for k, v in n.items() if k != "body"} | ({"body_chars": len(json.dumps(n["body"]))} if "body" in n else {}) for n in NET]
    (DEBUG / "network.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    big = [n for n in NET if "body" in n and re.search(r"calendar|release|episode|browse", n["url"])]
    (DEBUG / "api_samples.json").write_text(json.dumps([{"url": n["url"], "body": n["body"]} for n in big][:5], indent=1)[:200000], encoding="utf-8")
    return links


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def items_from_api():
    out, seen = [], set()
    for n in NET:
        if "body" not in n or not re.search(r"calendar|release|episode|browse", n["url"]):
            continue
        for d in walk(n["body"]):
            ep = d.get("episode_metadata") or d
            num = ep.get("episode_number") or ep.get("episode")
            series = ep.get("series_title") or d.get("series_title")
            title = d.get("title") or ep.get("title")
            ident = d.get("id") or ep.get("id")
            if not (series and title and ident) or ident in seen:
                continue
            seen.add(ident)
            link = f"https://www.crunchyroll.com/watch/{ident}"
            label = f"{series} — E{num}: {title}" if num else f"{series} — {title}"
            when = ep.get("episode_air_date") or ep.get("premium_available_date") or ep.get("availability_starts") or ""
            out.append({"title": label, "link": link, "img": "", "desc": f"{label} {when}".strip(), "when": when})
    out.sort(key=lambda i: i["when"], reverse=True)
    return out[:MAX_ITEMS]


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
    links = fetch_links()
    items = items_from_api() or build_items(links)
    print(f"{len(items)} items")
    if not items:
        print("No episodes found; see debug/ — feed left unchanged.", file=sys.stderr)
        sys.exit(1)
    write_feed(items)
