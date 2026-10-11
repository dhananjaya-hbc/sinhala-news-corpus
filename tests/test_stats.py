import importlib.util
from pathlib import Path

from collector.storage import append_rows

_spec = importlib.util.spec_from_file_location("stats", Path(__file__).parent.parent / "scripts" / "stats.py")
stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stats)


def _row(i, source, category):
    return {
        "date": "2026-10-11",
        "source": source,
        "headline": f"සිරස්තලය {i}",
        "category": category,
        "url": f"https://example.lk/{i}",
        "collected_at": "2026-10-11T01:00:00Z",
    }


def test_stats_counts_and_is_deterministic(tmp_path):
    data = tmp_path / "raw"
    append_rows(data, [_row(1, "dinamina", "sports"), _row(2, "dinamina", "local"), _row(3, "divaina", "local")])
    out = tmp_path / "STATS.md"
    stats.main(["--data-dir", str(data), "--config", str(tmp_path / "none.yaml"), "--out", str(out)])
    text = out.read_text(encoding="utf-8")

    assert "**Total headlines:** 3" in text
    assert "| dinamina | `dinamina` | 2 | 66.7% |" in text
    assert "| `local` | 2 | 66.7% |" in text
    assert "| `politics` | 0 | 0.0% |" in text

    stats.main(["--data-dir", str(data), "--config", str(tmp_path / "none.yaml"), "--out", str(out)])
    assert out.read_text(encoding="utf-8") == text


def test_stats_on_empty_data(tmp_path):
    out = tmp_path / "STATS.md"
    stats.main(["--data-dir", str(tmp_path / "raw"), "--config", str(tmp_path / "none.yaml"), "--out", str(out)])
    assert "**Total headlines:** 0" in out.read_text(encoding="utf-8")
