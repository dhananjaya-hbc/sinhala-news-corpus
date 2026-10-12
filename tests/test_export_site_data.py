import importlib.util
import json
from pathlib import Path

from collector.storage import append_rows

_spec = importlib.util.spec_from_file_location(
    "export_site_data", Path(__file__).parent.parent / "scripts" / "export_site_data.py"
)
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)

SOURCES = {"siyatha": {"name": "Siyatha News", "homepage": "https://siyathanews.lk/"}}


def _row(i, day, source="siyatha", category="sports", collected="2026-10-11T01:00:00Z"):
    return {
        "date": day,
        "source": source,
        "headline": f"සිරස්තලය {i}",
        "category": category,
        "url": f"https://siyathanews.lk/archives/{i}",
        "collected_at": collected,
    }


def test_keeps_only_last_n_days_newest_first():
    rows = [_row(1, "2026-09-01"), _row(2, "2026-10-10"), _row(3, "2026-10-11"), _row(4, "2026-10-02")]
    data = export.build(rows, SOURCES, days=10)
    assert [h["d"] for h in data["headlines"]] == ["2026-10-11", "2026-10-10", "2026-10-02"]
    assert data["total_all_time"] == 4


def test_first_and_last_collection_times():
    rows = [_row(1, "2026-10-11", collected="2026-10-12T01:00:00Z"), _row(2, "2026-10-01", collected="2026-10-11T01:00:00Z")]
    data = export.build(rows, SOURCES, days=30)
    assert data["first_collected"] == "2026-10-11T01:00:00Z"
    assert data["generated_from"] == "2026-10-12T01:00:00Z"


def test_summary_counts_and_source_names():
    rows = [_row(1, "2026-10-11"), _row(2, "2026-10-11", category="local"), _row(3, "2026-10-11", source="other")]
    data = export.build(rows, SOURCES, days=30)
    assert data["sources"][0] == {"id": "siyatha", "name": "Siyatha News", "homepage": "https://siyathanews.lk/", "count": 2}
    assert data["sources"][1]["name"] == "other"  # unknown id falls back to itself
    counts = {c["id"]: c["count"] for c in data["categories"]}
    assert counts["sports"] == 2 and counts["local"] == 1 and counts["politics"] == 0


def test_empty_data():
    data = export.build([], SOURCES, days=30)
    assert data["headlines"] == [] and data["total_all_time"] == 0


def test_main_writes_compact_utf8_json(tmp_path):
    append_rows(tmp_path / "raw", [_row(1, "2026-10-11")])
    out = tmp_path / "site-data.json"
    export.main(["--data-dir", str(tmp_path / "raw"), "--config", str(tmp_path / "none.yaml"), "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "සිරස්තලය 1" in text  # Sinhala written as-is, not \u escapes
    assert json.loads(text)["headlines"][0]["u"] == "https://siyathanews.lk/archives/1"


def test_stories_link_the_same_story_across_publishers():
    def r(i, source, headline):
        return {**_row(i, "2026-10-12", source=source), "headline": headline}

    rows = [
        r(1, "lankadeepa", "මහින්ද රෝහල් ගත කරයි"),
        r(2, "nethnews", "හිටපු ජනපති මහින්ද හදිසියේ රෝහල් ගත කෙරේ"),
        r(3, "ada", "කොළඹ මාර්ග හතකට මෙට්‍රෝ බස් 112ක්"),
        r(4, "siyatha", "ශ්‍රී ලංකා – පාකිස්ථාන විස්සයි විස්ස තරගාවලිය අදින් ඇරඹෙයි"),
    ]
    data = export.build(rows, SOURCES, days=30)
    assert len(data["stories"]) == 1
    story = data["stories"][0]
    assert story["publishers"] == 2
    assert {data["headlines"][i]["s"] for i in story["items"]} == {"lankadeepa", "nethnews"}
