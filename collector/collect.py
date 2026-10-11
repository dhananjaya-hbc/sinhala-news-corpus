"""Collect the latest headlines from every source in sources.yaml.

Usage:
    python -m collector.collect [--config sources.yaml] [--data-dir data/raw] [--dry-run]

Only feed metadata (title, link, categories, date) is read. Article pages
are never requested and article text is never stored.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

from collector.categories import pick_category
from collector.config import Config, Feed, Source, load_config
from collector.fetch import Fetcher, FetchError
from collector.sinhala_text import clean_headline, is_legacy_font_text, parse_sinhala_date
from collector.storage import SeenIndex, append_rows, clean_url, load_seen

log = logging.getLogger("collector")

SRI_LANKA_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Colombo")  # no DST
DELAY_BETWEEN_FEEDS = 1.0  # seconds, to stay gentle on each site


def entry_terms(entry) -> list[str]:
    return [t.get("term") or t.get("label") for t in entry.get("tags") or [] if t.get("term") or t.get("label")]


def entry_date(entry, now: datetime) -> str:
    """Publication date in Sri Lanka time, or today's date if the feed has none.

    Some feeds carry no pubDate at all (Ada Derana). Ada.lk writes it with
    Sinhala month names, which feedparser silently misreads ("2026 ඔක්තෝබර්
    මස 08 ..." becomes 2026-10-01), so the Sinhala format is tried first.
    """
    today = now.astimezone(SRI_LANKA_TZ).date()
    sinhala = parse_sinhala_date(entry.get("published") or entry.get("updated") or "")
    if sinhala:
        return (sinhala if sinhala <= today else today).isoformat()
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        published = datetime(*parsed[:6], tzinfo=timezone.utc)
        if published <= now + timedelta(days=1):  # ignore obviously wrong future dates
            return published.astimezone(SRI_LANKA_TZ).date().isoformat()
    return today.isoformat()


def process_entries(
    entries: Iterable,
    source: Source,
    feed: Feed,
    seen: SeenIndex,
    now: datetime,
    min_sinhala_ratio: float,
) -> tuple[list[dict[str, str]], Counter]:
    """Turn parsed feed entries into corpus rows, skipping bad and duplicate items."""
    rows: list[dict[str, str]] = []
    stats: Counter = Counter()
    collected_at = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for entry in entries:
        stats["entries"] += 1
        link = (entry.get("link") or "").strip()
        headline = clean_headline(entry.get("title") or "", source.title_suffixes)
        if not link or not headline:
            stats["skipped_empty"] += 1
            continue
        if is_legacy_font_text(headline, min_sinhala_ratio):
            stats["skipped_legacy"] += 1
            log.info("%s: skipped non-Sinhala/legacy-font headline: %r", source.id, headline[:80])
            continue
        url = clean_url(link)
        reason = seen.duplicate_reason(url, headline)
        if reason:
            stats[f"duplicate_{reason}"] += 1
            continue
        seen.add(url, headline)
        rows.append(
            {
                "date": entry_date(entry, now),
                "source": source.id,
                "headline": headline,
                "category": pick_category(entry_terms(entry), source.category_map, feed.default_category),
                "url": url,
                "collected_at": collected_at,
            }
        )
        stats["added"] += 1
    return rows, stats


def collect_source(
    source: Source, fetcher: Fetcher, seen: SeenIndex, now: datetime, min_sinhala_ratio: float
) -> tuple[list[dict[str, str]], Counter]:
    """Fetch every feed of one source. A failing feed is logged and skipped."""
    rows: list[dict[str, str]] = []
    stats: Counter = Counter()
    for i, feed in enumerate(source.feeds):
        if i:
            fetcher.sleep(DELAY_BETWEEN_FEEDS)
        try:
            parsed = feedparser.parse(fetcher.fetch_feed(feed.url))
            if parsed.bozo and not parsed.entries:
                raise FetchError(f"{feed.url}: not a valid feed ({parsed.get('bozo_exception')})")
            feed_rows, feed_stats = process_entries(parsed.entries, source, feed, seen, now, min_sinhala_ratio)
        except Exception as exc:  # one bad feed must not stop the others
            stats["feeds_failed"] += 1
            log.error("%s: feed failed: %s: %s", source.id, type(exc).__name__, exc)
            continue
        stats["feeds_ok"] += 1
        stats.update(feed_stats)
        rows.extend(feed_rows)
    if not stats["feeds_ok"]:
        raise FetchError(f"all {len(source.feeds)} feeds failed")
    return rows, stats


def collect(config: Config, data_dir: str | Path, fetcher: Fetcher, now: datetime | None = None, dry_run: bool = False) -> int:
    """Run one collection pass. Returns a process exit code."""
    now = now or datetime.now(timezone.utc)
    seen = load_seen(data_dir)
    log.info("loaded %d known URLs from %s", len(seen.urls), data_dir)

    all_rows: list[dict[str, str]] = []
    failed: list[str] = []
    for source in config.sources:
        try:
            rows, stats = collect_source(source, fetcher, seen, now, config.settings.min_sinhala_ratio)
        except Exception as exc:  # one bad source must not stop the others
            failed.append(source.id)
            log.error("%s: FAILED: %s", source.id, exc)
            continue
        all_rows.extend(rows)
        log.info("%s: %s", source.id, ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))

    if dry_run:
        log.info("dry run: %d new headlines not written", len(all_rows))
    else:
        for path, count in append_rows(data_dir, all_rows).items():
            log.info("wrote %d rows to %s", count, path)
    log.info("done: %d new headlines, %d/%d sources failed %s", len(all_rows), len(failed), len(config.sources), failed or "")
    return 1 if config.sources and len(failed) == len(config.sources) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="sources.yaml")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, but write nothing")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stdout)
    config = load_config(args.config)
    s = config.settings
    fetcher = Fetcher(s.user_agent, timeout=s.timeout, retries=s.retries, backoff=s.backoff)
    return collect(config, args.data_dir, fetcher, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
