"""Monthly CSV storage (data/raw/YYYY-MM.csv) and the duplicate index."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from collector.sinhala_text import headline_key

FIELDS = ("date", "source", "headline", "category", "url", "collected_at")

_TRACKING_PARAMS = {"fbclid", "gclid", "at_medium", "at_campaign", "at_custom1", "at_custom2", "at_custom3", "at_custom4"}


def _is_tracking(param: str) -> bool:
    return param.lower().startswith("utm_") or param.lower() in _TRACKING_PARAMS


def clean_url(url: str) -> str:
    """Drop the fragment and tracking parameters (utm_*, BBC's at_*)."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))


def url_key(url: str) -> str:
    """Comparison key for URLs.

    Ignores http/https, a leading "www.", a trailing slash and
    percent-encoding, so Mawbima's %e0%b6%b1... links and the same link
    written in raw Sinhala compare equal.
    """
    parts = urlsplit(clean_url(url))
    host = parts.netloc.removeprefix("www.")
    path = unquote(parts.path).rstrip("/")
    query = f"?{unquote(parts.query)}" if parts.query else ""
    return f"{host}{path}{query}"


@dataclass
class SeenIndex:
    urls: set[str] = field(default_factory=set)
    headlines: set[str] = field(default_factory=set)

    def duplicate_reason(self, url: str, headline: str) -> str | None:
        if url_key(url) in self.urls:
            return "url"
        if headline_key(headline) in self.headlines:
            return "headline"
        return None

    def add(self, url: str, headline: str) -> None:
        self.urls.add(url_key(url))
        self.headlines.add(headline_key(headline))


def month_files(data_dir: str | Path) -> list[Path]:
    return sorted(Path(data_dir).glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].csv"))


def read_rows(data_dir: str | Path) -> Iterable[dict[str, str]]:
    for path in month_files(data_dir):
        with open(path, encoding="utf-8", newline="") as fh:
            yield from csv.DictReader(fh)


def load_seen(data_dir: str | Path) -> SeenIndex:
    """Index every URL and headline already stored, across all months."""
    seen = SeenIndex()
    for row in read_rows(data_dir):
        seen.add(row["url"], row["headline"])
    return seen


def append_rows(data_dir: str | Path, rows: Iterable[dict[str, str]]) -> dict[Path, int]:
    """Append rows to the file for the month they were collected in.

    Files are append-only, so each day's commit is a small diff.
    Returns the number of rows written per file.
    """
    data_dir = Path(data_dir)
    by_month: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_month[row["collected_at"][:7]].append(row)

    written = {}
    for month, month_rows in sorted(by_month.items()):
        path = data_dir / f"{month}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists() or path.stat().st_size == 0
        with open(path, "a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            if new_file:
                writer.writeheader()
            writer.writerows({k: row[k] for k in FIELDS} for row in month_rows)
        written[path] = len(month_rows)
    return written
