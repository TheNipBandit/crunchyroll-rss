"""Always-on server: refreshes recent Crunchyroll episodes from AniList every
couple of minutes and serves the feed + episode page.

Environment variables (all optional):
  PORT              port to listen on (Railway sets this)      default 8080
  REFRESH_SECONDS   how often to re-query AniList              default 120
  DAYS_TO_SCAN      how many days back to list                 default from config.json
  FEED_TIMEZONE     timezone for displayed times               default from config.json
  SITE_URL          public base URL (else RAILWAY_PUBLIC_DOMAIN is used)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from anilist_source import fetch_recent  # noqa: E402
from rss_generator import write_feeds  # noqa: E402

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TIMEZONE = os.getenv("FEED_TIMEZONE", CONFIG.get("timezone", "America/New_York"))
DAYS = int(os.getenv("DAYS_TO_SCAN", CONFIG.get("days_to_scan", 7)))
REFRESH = max(30, int(os.getenv("REFRESH_SECONDS", "120")))
PORT = int(os.getenv("PORT", "8080"))
_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
SITE_URL = os.getenv("SITE_URL", f"https://{_domain}" if _domain else "").rstrip("/")

CONTENT_TYPES = {
    ".xml": "application/rss+xml; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}

_lock = threading.Lock()
_current: Path | None = None
_updated = 0.0


def refresh_once() -> int:
    """Rebuild the site into a fresh directory and swap it in. Returns item count."""
    global _current, _updated
    rows = fetch_recent(days_back=DAYS)
    if not rows:
        raise RuntimeError("AniList returned no Crunchyroll releases")
    new_dir = Path(tempfile.mkdtemp(prefix="site-"))
    try:
        count = write_feeds(
            rows=rows,
            output_dir=new_dir,
            timezone_name=TIMEZONE,
            feed_title=CONFIG.get("feed_title", "Crunchyroll Episode Releases"),
            feed_description=CONFIG.get("feed_description", "Recently released Crunchyroll episodes."),
            site_url=SITE_URL,
        )
    except Exception:
        shutil.rmtree(new_dir, ignore_errors=True)
        raise
    with _lock:
        old, _current, _updated = _current, new_dir, time.time()
    if old:
        shutil.rmtree(old, ignore_errors=True)
    return count


def refresh_loop() -> None:
    while True:
        try:
            print(f"refreshed: {refresh_once()} episodes", flush=True)
        except Exception as exc:  # keep serving the last good copy
            print(f"refresh failed: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(REFRESH)


class Handler(BaseHTTPRequestHandler):
    server_version = "crunchyroll-rss"

    def _send(self, status: int, body: bytes, ctype: str, head: bool = False, extra=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=60")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _serve(self, head: bool) -> None:
        path = self.path.split("?")[0].split("#")[0]
        if path == "/healthz":
            return self._send(200, b"ok", "text/plain", head)
        with _lock:
            base = _current
        if base is None:
            return self._send(503, b"Starting up, try again in a moment.", "text/plain", head,
                              {"Retry-After": "10"})
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (base / rel).resolve()
        if base.resolve() not in target.parents or not target.is_file():
            return self._send(404, b"Not found", "text/plain", head)
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype, head)

    def do_GET(self) -> None:  # noqa: N802
        self._serve(False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(True)

    def log_message(self, fmt, *args) -> None:  # quieter logs
        pass


def main() -> None:
    threading.Thread(target=refresh_loop, daemon=True).start()
    print(f"listening on :{PORT}, refreshing every {REFRESH}s", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
