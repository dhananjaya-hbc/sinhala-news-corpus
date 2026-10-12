import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("source_alerts", Path(__file__).parent.parent / "scripts" / "source_alerts.py")
alerts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alerts)

NAMES = {"ada": "Ada (ada.lk)", "nethnews": "Neth News"}
ADA_FEED = "https://www.ada.lk/rss/sports/9"


def health(days, source="ada", url=ADA_FEED, error="FetchError: HTTP 403 (server: cloudflare)"):
    return {"failing": {url: {"source": source, "since": days[0], "days": days, "last_error": error}}}


def test_one_bad_day_is_not_an_alert():
    assert alerts.plan(health(["2026-10-12"]), [], NAMES) == []


def test_two_bad_days_open_an_issue():
    [(kind, title, body)] = alerts.plan(health(["2026-10-12", "2026-10-13"]), [], NAMES)
    assert kind == "create"
    assert title == "Source failing: Ada (ada.lk) [ada]"
    assert ADA_FEED in body and "HTTP 403" in body and "since 2026-10-12" in body


def test_existing_issue_is_updated_not_duplicated():
    h = health(["2026-10-12", "2026-10-13", "2026-10-14"])
    issue = {"number": 7, "title": "Source failing: Ada (ada.lk) [ada]", "body": "old text"}
    assert alerts.plan(h, [issue], NAMES) == [("edit", 7, alerts.issue_body("ada", "Ada (ada.lk)", list(h["failing"].items())))]


def test_unchanged_issue_needs_no_action():
    h = health(["2026-10-12", "2026-10-13"])
    body = alerts.issue_body("ada", "Ada (ada.lk)", list(h["failing"].items()))
    assert alerts.plan(h, [{"number": 7, "title": "Source failing: Ada (ada.lk) [ada]", "body": body}], NAMES) == []


def test_recovered_source_issue_is_closed():
    issue = {"number": 7, "title": "Source failing: Ada (ada.lk) [ada]", "body": "..."}
    [(kind, number, _)] = alerts.plan({"failing": {}}, [issue], NAMES)
    assert (kind, number) == ("close", 7)


def test_issue_stays_open_while_still_failing_below_threshold():
    # a feed failed again today after a fix attempt: keep the issue open
    issue = {"number": 7, "title": "Source failing: Ada (ada.lk) [ada]", "body": "..."}
    assert alerts.plan(health(["2026-10-15"]), [issue], NAMES) == []


def test_unrelated_issues_are_ignored():
    issue = {"number": 3, "title": "Add BBC Sinhala as a source", "body": ""}
    assert alerts.plan({"failing": {}}, [issue], NAMES) == []


def test_pipes_in_errors_do_not_break_the_table():
    h = health(["2026-10-12", "2026-10-13"], error="weird | error")
    [(_, _, body)] = alerts.plan(h, [], NAMES)
    assert "weird / error" in body
