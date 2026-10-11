"""Check that feeds are reachable and return Sinhala headlines from this network.

Usage: python scripts/check_feeds.py [FEED_URL ...]

With no URLs, every feed in sources.yaml is checked. Some publishers block
cloud IP ranges, so a feed that works from a laptop can still fail on GitHub
Actions; run this through the "Check feeds" workflow before adding a source.
Writes a Markdown table to stdout (and to the job summary on GitHub Actions).
Nothing is stored.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import feedparser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import load_config  # noqa: E402
from collector.fetch import Fetcher  # noqa: E402
from collector.sinhala_text import clean_headline, sinhala_ratio  # noqa: E402


def check(fetcher: Fetcher, url: str) -> list[str]:
    try:
        parsed = feedparser.parse(fetcher.fetch_feed(url))
    except Exception as exc:
        return [url, "FAIL", "-", "-", "-", f"{type(exc).__name__}: {exc}"[:140]]
    titles = [clean_headline(e.get("title") or "") for e in parsed.entries]
    if not titles:
        return [url, "FAIL", "0", "-", "-", f"not a feed ({parsed.get('bozo_exception')})"[:140]]
    tags = Counter(t.get("term") for e in parsed.entries for t in e.get("tags") or [] if t.get("term"))
    top_tags = ", ".join(t for t, _ in tags.most_common(4)) or "none"
    ratio = f"{sinhala_ratio(' '.join(titles)):.2f}"
    return [url, "OK", str(len(titles)), ratio, top_tags, titles[0][:60]]


def main(argv: list[str]) -> int:
    config = load_config("sources.yaml")
    urls = argv or [feed.url for source in config.sources for feed in source.feeds]
    s = config.settings
    fetcher = Fetcher(s.user_agent, timeout=s.timeout, retries=1, backoff=s.backoff)

    lines = [
        "| Feed | Status | Items | Sinhala ratio | Top tags | First headline / error |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for url in urls:
        cells = [c.replace("|", "\\|") for c in check(fetcher, url)]
        lines.append("| " + " | ".join(cells) + " |")
    report = "\n".join(lines) + "\n"

    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Feed check\n\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
