"""Re-apply the current cleaning rules to headlines already stored.

Usage: python scripts/reclean.py [--data-dir data/raw] [--dry-run]

Run this after improving collector/sinhala_text.py so older rows match the
new rules. Only the `headline` column is rewritten; rows are never added,
removed or reordered. Prints every change for review.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.sinhala_text import clean_headline  # noqa: E402
from collector.storage import FIELDS, month_files  # noqa: E402


def reclean_file(path: Path, dry_run: bool) -> int:
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    changed = 0
    for row in rows:
        cleaned = clean_headline(row["headline"])
        if cleaned != row["headline"]:
            changed += 1
            print(f"{path.name}: {row['url']}\n  - {row['headline']}\n  + {cleaned}")
            row["headline"] = cleaned
    if changed and not dry_run:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-clean stored headlines")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--dry-run", action="store_true", help="show changes without writing")
    args = parser.parse_args(argv)

    total = sum(reclean_file(path, args.dry_run) for path in month_files(args.data_dir))
    print(f"{total} headline(s) {'would change' if args.dry_run else 'updated'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
