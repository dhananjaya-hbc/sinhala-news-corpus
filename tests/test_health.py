from collector.health import load_health, save_health, update_health

ADA = "https://www.ada.lk/rss/sports/9"
NETH = "https://www.nethnews.lk/feed/"


def test_healthy_run_records_nothing():
    assert update_health({"failing": {}}, {ADA: ("ada", None), NETH: ("nethnews", None)}, "2026-10-12") == {"failing": {}}


def test_failure_is_recorded_with_first_day():
    health = update_health({}, {ADA: ("ada", "FetchError: HTTP 403 (server: cloudflare)")}, "2026-10-12")
    assert health["failing"][ADA] == {
        "source": "ada",
        "since": "2026-10-12",
        "days": ["2026-10-12"],
        "last_error": "FetchError: HTTP 403 (server: cloudflare)",
    }


def test_failing_days_accumulate_once_per_day():
    h = update_health({}, {ADA: ("ada", "HTTP 403")}, "2026-10-12")
    h = update_health(h, {ADA: ("ada", "HTTP 403")}, "2026-10-12")  # backup run, same day
    h = update_health(h, {ADA: ("ada", "HTTP 503")}, "2026-10-13")
    assert h["failing"][ADA]["days"] == ["2026-10-12", "2026-10-13"]
    assert h["failing"][ADA]["since"] == "2026-10-12"
    assert h["failing"][ADA]["last_error"] == "HTTP 503"


def test_recovered_feed_is_removed():
    h = update_health({}, {ADA: ("ada", "HTTP 403")}, "2026-10-12")
    h = update_health(h, {ADA: ("ada", None)}, "2026-10-13")
    assert h == {"failing": {}}


def test_feed_not_tried_is_dropped():
    h = update_health({}, {ADA: ("ada", "HTTP 403")}, "2026-10-12")
    assert update_health(h, {NETH: ("nethnews", None)}, "2026-10-13") == {"failing": {}}


def test_save_only_when_changed(tmp_path):
    path = tmp_path / "health.json"
    assert not save_health(path, {"failing": {}})  # healthy and no file yet: don't create one
    assert not path.exists()
    h = update_health({}, {ADA: ("ada", "HTTP 403")}, "2026-10-12")
    assert save_health(path, h)
    assert not save_health(path, h)
    assert load_health(path) == h
    assert save_health(path, {"failing": {}})  # recovery is written
    assert load_health(path) == {"failing": {}}


def test_missing_file_loads_as_healthy(tmp_path):
    assert load_health(tmp_path / "nope.json") == {"failing": {}}
