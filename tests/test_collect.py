"""End-to-end collector tests with in-memory feeds; no network access."""

import csv
from datetime import datetime, timezone

import feedparser

from collector.categories import build_category_map
from collector.collect import collect, entry_date, process_entries
from collector.config import Config, Feed, Settings, Source
from collector.fetch import FetchError
from collector.storage import SeenIndex

NOW = datetime(2026, 10, 11, 1, 0, 0, tzinfo=timezone.utc)

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title>
<item>
  <title>ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක් - Ada Derana Sinhala</title>
  <link>https://sinhala.adaderana.lk/news/252848</link>
  <category>hot-news</category>
  <description>full article text that must never be stored</description>
</item>
<item>
  <title>ශ්‍රී ලංකා - පාකිස්ථාන විස්සයි විස්ස තරගාවලිය අදින් ඇරඹෙයි</title>
  <link>https://sinhala.adaderana.lk/news/252849</link>
  <category>sports-news</category>
  <pubDate>Sat, 10 Oct 2026 20:00:00 +0000</pubDate>
</item>
<item>
  <title>Y%S ,xld rch wo</title>
  <link>https://sinhala.adaderana.lk/news/252850</link>
</item>
<item>
  <title>ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක්!</title>
  <link>https://sinhala.adaderana.lk/news/999999</link>
</item>
<item>
  <title></title>
  <link>https://sinhala.adaderana.lk/news/1</link>
</item>
</channel></rss>"""

SETTINGS = Settings(user_agent="sinhala-news-corpus/1.0 (+test)", retries=0)
ADA = Source(
    id="adaderana",
    name="Ada Derana Sinhala",
    homepage="https://sinhala.adaderana.lk/",
    feeds=(Feed("https://sinhala.adaderana.lk/rss.php", "other"),),
    category_map=build_category_map({"hot-news": "local", "sports-news": "sports"}),
    title_suffixes=("Ada Derana Sinhala",),
)
BROKEN = Source(id="broken", name="Broken", homepage="", feeds=(Feed("https://broken.example/feed"),))


class FakeFetcher:
    def __init__(self, feeds):
        self.feeds = feeds
        self.requested = []

    def fetch_feed(self, url):
        self.requested.append(url)
        if url not in self.feeds:
            raise FetchError(f"{url}: HTTP 503")
        return self.feeds[url].encode("utf-8")

    def sleep(self, seconds):
        pass


def test_process_entries_cleans_labels_and_skips():
    entries = feedparser.parse(RSS).entries
    rows, stats = process_entries(entries, ADA, ADA.feeds[0], SeenIndex(), NOW, 0.5)

    assert [r["headline"] for r in rows] == [
        "ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක්",
        "ශ්‍රී ලංකා - පාකිස්ථාන විස්සයි විස්ස තරගාවලිය අදින් ඇරඹෙයි",
    ]
    assert [r["category"] for r in rows] == ["local", "sports"]
    assert stats["skipped_legacy"] == 1
    assert stats["duplicate_headline"] == 1
    assert stats["skipped_empty"] == 1
    assert set(rows[0]) == {"date", "source", "headline", "category", "url", "collected_at"}
    assert rows[0]["collected_at"] == "2026-10-11T01:00:00Z"


def test_dates_use_sri_lanka_time_and_fall_back_to_today():
    entries = feedparser.parse(RSS).entries
    # no pubDate -> collection date in Sri Lanka
    assert entry_date(entries[0], NOW) == "2026-10-11"
    # 20:00 UTC on the 10th is 01:30 on the 11th in Colombo
    assert entry_date(entries[1], NOW) == "2026-10-11"


def test_sinhala_pubdate_is_parsed():
    # Ada.lk writes pubDate with Sinhala month names
    rss = RSS.replace("<category>hot-news</category>", "<pubDate>2026 ඔක්තෝබර් මස 08 ප.ව. 06:19</pubDate>")
    entry = feedparser.parse(rss).entries[0]
    assert entry_date(entry, NOW) == "2026-10-08"


def test_failing_source_does_not_stop_others(tmp_path):
    config = Config(settings=SETTINGS, sources=(BROKEN, ADA))
    fetcher = FakeFetcher({ADA.feeds[0].url: RSS})
    assert collect(config, tmp_path, fetcher, now=NOW) == 0
    assert BROKEN.feeds[0].url in fetcher.requested
    with open(tmp_path / "2026-10.csv", encoding="utf-8", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 2


def test_all_sources_failing_returns_error(tmp_path):
    config = Config(settings=SETTINGS, sources=(BROKEN,))
    assert collect(config, tmp_path, FakeFetcher({}), now=NOW) == 1


def test_second_run_adds_no_duplicates(tmp_path):
    config = Config(settings=SETTINGS, sources=(ADA,))
    fetcher = FakeFetcher({ADA.feeds[0].url: RSS})
    collect(config, tmp_path, fetcher, now=NOW)
    collect(config, tmp_path, fetcher, now=NOW.replace(hour=7))
    with open(tmp_path / "2026-10.csv", encoding="utf-8", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 2


def test_dry_run_writes_nothing(tmp_path):
    config = Config(settings=SETTINGS, sources=(ADA,))
    collect(config, tmp_path, FakeFetcher({ADA.feeds[0].url: RSS}), now=NOW, dry_run=True)
    assert not list(tmp_path.iterdir())


def test_article_text_never_stored(tmp_path):
    config = Config(settings=SETTINGS, sources=(ADA,))
    collect(config, tmp_path, FakeFetcher({ADA.feeds[0].url: RSS}), now=NOW)
    assert "full article text" not in (tmp_path / "2026-10.csv").read_text(encoding="utf-8")


def test_failing_feeds_are_remembered_in_health_file(tmp_path):
    import json

    health = tmp_path / "health.json"
    config = Config(settings=SETTINGS, sources=(BROKEN, ADA))
    fetcher = FakeFetcher({ADA.feeds[0].url: RSS})
    collect(config, tmp_path / "raw", fetcher, now=NOW, health_path=health)
    state = json.loads(health.read_text(encoding="utf-8"))
    assert list(state["failing"]) == [BROKEN.feeds[0].url]
    entry = state["failing"][BROKEN.feeds[0].url]
    assert entry["source"] == "broken" and entry["days"] == ["2026-10-11"]
    assert "HTTP 503" in entry["last_error"]


def test_healthy_run_creates_no_health_file(tmp_path):
    health = tmp_path / "health.json"
    config = Config(settings=SETTINGS, sources=(ADA,))
    collect(config, tmp_path / "raw", FakeFetcher({ADA.feeds[0].url: RSS}), now=NOW, health_path=health)
    assert not health.exists()


def test_dry_run_does_not_touch_health_file(tmp_path):
    health = tmp_path / "health.json"
    config = Config(settings=SETTINGS, sources=(BROKEN,))
    collect(config, tmp_path / "raw", FakeFetcher({}), now=NOW, dry_run=True, health_path=health)
    assert not health.exists()
