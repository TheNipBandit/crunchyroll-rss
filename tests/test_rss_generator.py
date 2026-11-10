import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rss_generator import normalize_release, write_feeds


class RSSGeneratorTests(unittest.TestCase):
    def test_normalize_release_uses_eastern_weekday(self):
        tz = ZoneInfo("America/New_York")
        item = normalize_release({
            "episode_title": "Example Episode",
            "episode_number": "4",
            "release_time": "2026-11-10T18:00:00Z",
            "episode_url": "/watch/example",
            "thumbnail": "https://img.example/poster.jpg",
            "premium": False,
        }, tz)
        self.assertEqual(item["weekday"], "tuesday")
        self.assertEqual(item["title"], "Example Episode")
        self.assertIn("Episode number: 4", item["description"])

    def test_writes_main_and_weekday_feeds(self):
        rows = [{
            "episode_title": "Example Episode",
            "episode_number": "4",
            "release_time": "2026-11-10T18:00:00Z",
            "episode_url": "https://www.crunchyroll.com/watch/example",
            "thumbnail": "",
            "premium": False,
        }]
        with tempfile.TemporaryDirectory() as temp:
            count = write_feeds(rows, Path(temp), "America/New_York",
                                "Test feed", "Test description",
                                "https://example.github.io/feed")
            self.assertEqual(count, 1)
            root = ET.parse(Path(temp) / "index.xml").getroot()
            self.assertEqual(len(root.findall("./channel/item")), 1)
            tuesday = ET.parse(Path(temp) / "feeds/tuesday.xml").getroot()
            self.assertEqual(len(tuesday.findall("./channel/item")), 1)
            monday = ET.parse(Path(temp) / "feeds/monday.xml").getroot()
            self.assertEqual(len(monday.findall("./channel/item")), 0)


if __name__ == "__main__":
    unittest.main()
