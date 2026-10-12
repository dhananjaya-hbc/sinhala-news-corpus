"""Open, update or close GitHub issues for news sources whose feeds keep failing.

Usage: python scripts/source_alerts.py [--health data/health.json] [--config sources.yaml]
                                       [--min-days 2] [--dry-run]

Runs in the daily workflow after collection. A source gets an issue once one
of its feeds has failed on --min-days different days in a row; GitHub emails
the repository owner. The issue is updated while the problem lasts and closed
automatically when the feeds work again. Needs the `gh` CLI with GH_TOKEN
(issues: write). One issue per source, titled "Source failing: <name> [<id>]".
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.health import load_health  # noqa: E402

LABEL = "source-failure"
TITLE_ID = re.compile(r"\[([A-Za-z0-9_-]+)\]\s*$")
SRI_LANKA_TZ = timezone(timedelta(hours=5, minutes=30))


def failing_sources(health: dict, min_days: int) -> dict[str, list[tuple[str, dict]]]:
    """Source id -> failing feeds (url, entry) that have failed on at least min_days days."""
    out: dict[str, list[tuple[str, dict]]] = {}
    for url, entry in sorted(health.get("failing", {}).items()):
        if len(entry.get("days", [])) >= min_days:
            out.setdefault(entry["source"], []).append((url, entry))
    return out


def issue_title(source_id: str, name: str) -> str:
    return f"Source failing: {name} [{source_id}]"


def issue_body(source_id: str, name: str, feeds: list[tuple[str, dict]]) -> str:
    since = min(entry["since"] for _, entry in feeds)
    rows = "\n".join(
        f"| {url} | {entry['since']} | {len(entry['days'])} | `{entry['last_error'].replace('|', '/').replace('`', "'")[:200]}` |"
        for url, entry in feeds
    )
    return f"""**{name}** (`{source_id}`) has {len(feeds)} feed(s) that keep failing, since {since}.

| Feed | Failing since | Days failed | Last error |
|---|---|---|---|
{rows}

The collector keeps running the other sources, so their data is not affected.

**What to check**
- Run the **Check feeds** workflow (Actions → Check feeds → Run workflow) with these URLs to see whether GitHub's network can reach them.
- HTTP 403: the site may now block GitHub's servers. HTTP 404: the feed has probably moved.
- Update the URL in `sources.yaml`, or pause the source with `enabled: false`.

This issue closes itself when the feeds work again.

_Opened automatically by the daily collection workflow._"""


def plan(health: dict, open_issues: list[dict], names: dict[str, str], min_days: int = 2) -> list[tuple]:
    """Decide what to do with issues. Returns ("create", title, body),
    ("edit", number, body) and ("close", number, comment) actions."""
    failing = failing_sources(health, min_days)
    by_source = {}
    for issue in open_issues:
        match = TITLE_ID.search(issue["title"])
        if match:
            by_source.setdefault(match.group(1), issue)

    actions: list[tuple] = []
    for source_id, feeds in failing.items():
        name = names.get(source_id, source_id)
        body = issue_body(source_id, name, feeds)
        issue = by_source.get(source_id)
        if issue is None:
            actions.append(("create", issue_title(source_id, name), body))
        elif issue.get("body", "").strip() != body.strip():
            actions.append(("edit", issue["number"], body))
    for source_id, issue in sorted(by_source.items()):
        if source_id not in failing and not any(e["source"] == source_id for e in health.get("failing", {}).values()):
            actions.append(("close", issue["number"], "All feeds of this source are working again. Closing automatically."))
    return actions


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open or close issues for failing news sources")
    parser.add_argument("--health", default="data/health.json")
    parser.add_argument("--config", default="sources.yaml")
    parser.add_argument("--min-days", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="print the actions instead of calling GitHub")
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        names = {s["id"]: s.get("name", s["id"]) for s in yaml.safe_load(fh)["sources"]}
    health = load_health(args.health)
    if args.dry_run:
        open_issues = []
    else:
        open_issues = json.loads(gh("issue", "list", "--label", LABEL, "--state", "open", "--json", "number,title,body", "--limit", "100"))

    actions = plan(health, open_issues, names, args.min_days)
    if not actions:
        print("No source alerts to open, update or close.")
    for action in actions:
        kind, target, text = action
        print(f"{kind}: {target}")
        if args.dry_run:
            continue
        if kind == "create":
            gh("label", "create", LABEL, "--color", "B60205", "--description", "A news feed keeps failing", "--force")
            gh("issue", "create", "--title", target, "--body", text, "--label", LABEL)
        elif kind == "edit":
            gh("issue", "edit", str(target), "--body", text)
        elif kind == "close":
            gh("issue", "close", str(target), "--comment", text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
