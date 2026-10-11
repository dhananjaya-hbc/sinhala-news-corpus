import csv

from collector.storage import FIELDS, SeenIndex, append_rows, clean_url, load_seen, url_key


def row(url, headline, collected_at="2026-10-11T01:00:00Z", **extra):
    return {
        "date": "2026-10-11",
        "source": "dinamina",
        "headline": headline,
        "category": "local",
        "url": url,
        "collected_at": collected_at,
        **extra,
    }


def test_clean_url_drops_tracking_and_fragment():
    url = "https://www.bbc.com/sinhala/articles/cm17kq007g0zo?at_medium=RSS&at_campaign=rss#top"
    assert clean_url(url) == "https://www.bbc.com/sinhala/articles/cm17kq007g0zo"
    assert clean_url("https://lankatruth.com/si/?p=205460&utm_source=rss") == "https://lankatruth.com/si/?p=205460"


def test_url_key_ignores_encoding_scheme_www_and_slash():
    encoded = "https://mawbima.lk/2026/10/11/%e0%b6%85%e0%b6%af/"
    raw = "http://www.mawbima.lk/2026/10/11/අද"
    assert url_key(encoded) == url_key(raw)


def test_url_key_keeps_query_ids_apart():
    assert url_key("https://lankatruth.com/si/?p=1") != url_key("https://lankatruth.com/si/?p=2")


def test_seen_index_detects_url_and_headline_duplicates():
    seen = SeenIndex()
    seen.add("https://www.divaina.lk/main-news/107664", "ඥානසාර හිමිට නිදහස පතා සඟ පා ගමනක්")
    assert seen.duplicate_reason("https://divaina.lk/main-news/107664/", "වෙනත් සිරස්තලයක්") == "url"
    # same story, another URL, different spacing and punctuation
    assert seen.duplicate_reason("https://www.divaina.lk/main-news/999", "ඥානසාර හිමිට  නිදහස පතා සඟ පා ගමනක්!") == "headline"
    assert seen.duplicate_reason("https://www.divaina.lk/main-news/1000", "අද සවසට වැස්ස") is None


def test_append_creates_monthly_files_with_header(tmp_path):
    written = append_rows(
        tmp_path,
        [
            row("https://a.lk/1", "පළමු", collected_at="2026-09-30T01:00:00Z"),
            row("https://a.lk/2", "දෙවන", collected_at="2026-10-01T01:00:00Z"),
        ],
    )
    assert {p.name: n for p, n in written.items()} == {"2026-09.csv": 1, "2026-10.csv": 1}
    with open(tmp_path / "2026-10.csv", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assert lines[0] == ",".join(FIELDS)
    assert lines[1].endswith("https://a.lk/2,2026-10-01T01:00:00Z")


def test_append_twice_writes_header_once_and_roundtrips_sinhala(tmp_path):
    headline = 'ශ්‍රී ලංකා - පාකිස්ථාන "විස්සයි විස්ස", තරගාවලිය'
    append_rows(tmp_path, [row("https://a.lk/1", headline)])
    append_rows(tmp_path, [row("https://a.lk/2", "අද සවසට වැස්ස")])
    with open(tmp_path / "2026-10.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["headline"] for r in rows] == [headline, "අද සවසට වැස්ස"]


def test_extra_keys_not_written(tmp_path):
    append_rows(tmp_path, [row("https://a.lk/1", "පළමු", summary="full article text")])
    content = (tmp_path / "2026-10.csv").read_text(encoding="utf-8")
    assert "full article text" not in content


def test_load_seen_reads_all_months(tmp_path):
    append_rows(tmp_path, [row("https://a.lk/1", "පළමු", collected_at="2026-09-30T01:00:00Z")])
    append_rows(tmp_path, [row("https://a.lk/2", "දෙවන")])
    seen = load_seen(tmp_path)
    assert seen.duplicate_reason("https://a.lk/1", "x") == "url"
    assert seen.duplicate_reason("https://a.lk/9", "දෙවන") == "headline"


def test_load_seen_empty_dir(tmp_path):
    assert load_seen(tmp_path / "missing").urls == set()
