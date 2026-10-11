"""Export recent headlines as JSON for the website (site/).

Usage: python scripts/export_site_data.py [--data-dir data/raw] [--config sources.yaml]
                                          [--out site/src/data/site-data.json] [--days 30]

The site only shows the last N days; the full history stays in data/raw/.
The output depends only on the data, so rebuilding is reproducible.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.categories import LABELS  # noqa: E402
from collector.storage import read_rows  # noqa: E402


def build(rows: list[dict[str, str]], sources: dict[str, dict[str, str]], days: int) -> dict:
    """Select headlines from the last ``days`` days (relative to the newest one) and summarise."""
    if not rows:
        return {"generated_from": None, "first_collected": None, "days": days, "total_all_time": 0, "headlines": [], "sources": [], "categories": []}

    newest = max(date.fromisoformat(r["date"]) for r in rows)
    cutoff = (newest - timedelta(days=days - 1)).isoformat()
    recent = [r for r in rows if r["date"] >= cutoff]
    # newest first; within a day, most recently collected first; url breaks ties
    recent.sort(key=lambda r: (r["date"], r["collected_at"], r["url"]), reverse=True)

    by_source = Counter(r["source"] for r in rows)
    by_category = Counter(r["category"] for r in rows)
    return {
        "generated_from": max(r["collected_at"] for r in rows),
        "first_collected": min(r["collected_at"] for r in rows),  # day 1 of the corpus, for edition numbers
        "days": days,
        "total_all_time": len(rows),
        "headlines": [
            {"d": r["date"], "s": r["source"], "c": r["category"], "h": r["headline"], "u": r["url"]} for r in recent
        ],
        "sources": [
            {"id": sid, "name": sources.get(sid, {}).get("name", sid), "homepage": sources.get(sid, {}).get("homepage", ""), "count": n}
            for sid, n in sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "categories": [{"id": c, "count": by_category[c]} for c in LABELS],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export recent headlines for the website")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--config", default="sources.yaml")
    parser.add_argument("--out", default="site/src/data/site-data.json")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)

    sources = {}
    if Path(args.config).exists():
        # read the YAML directly so disabled sources keep their display names
        with open(args.config, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        sources = {s["id"]: {"name": s.get("name", s["id"]), "homepage": s.get("homepage", "")} for s in raw["sources"]}

    data = build(list(read_rows(args.data_dir)), sources, args.days)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out}: {len(data['headlines'])} headlines from the last {args.days} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
