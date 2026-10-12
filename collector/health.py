"""Remember which feeds are failing, across runs, in data/health.json.

Only failing feeds are recorded, so on a healthy day the file does not
change and causes no commit. A feed that works again is removed.

    {"failing": {"<feed url>": {"source": "ada", "since": "2026-10-12",
                                "days": ["2026-10-12", "2026-10-13"],
                                "last_error": "FetchError: ... HTTP 403"}}}
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

MAX_DAYS_KEPT = 14


def update_health(health: Mapping, results: Mapping[str, tuple[str, str | None]], today: str) -> dict:
    """Return the new health state after one run.

    ``results`` maps each feed URL that was tried to ``(source_id, error)``,
    where ``error`` is None if the feed worked. Feeds that were not tried
    (e.g. removed from sources.yaml) are dropped.
    """
    previous = health.get("failing", {})
    failing = {}
    for url, (source, error) in sorted(results.items()):
        if error is None:
            continue
        entry = previous.get(url, {})
        days = sorted(set(entry.get("days", [])) | {today})[-MAX_DAYS_KEPT:]
        failing[url] = {"source": source, "since": entry.get("since", today), "days": days, "last_error": error}
    return {"failing": failing}


def load_health(path: str | Path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"failing": {}}


def save_health(path: str | Path, health: dict) -> bool:
    """Write the file only if something changed. Returns True if written."""
    path = Path(path)
    if health == load_health(path) and (path.exists() or not health["failing"]):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
