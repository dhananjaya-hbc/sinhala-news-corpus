"""Story grouping tests on a real snapshot of the corpus (fixtures/corpus_2026-10-12.csv).

IDF is learned from the whole snapshot, as the website export does, and stories
are found among the headlines of 11-12 October 2026.
"""

import csv
from pathlib import Path

import pytest

from collector.stories import Vectorizer, char_ngrams, cosine, find_stories

FIXTURE = Path(__file__).parent / "fixtures" / "corpus_2026-10-12.csv"

with open(FIXTURE, encoding="utf-8", newline="") as fh:
    CORPUS = list(csv.DictReader(fh))
RECENT = [r for r in CORPUS if r["date"] in ("2026-10-11", "2026-10-12")]
TEXTS = [r["headline"] for r in RECENT]
SOURCES = [r["source"] for r in RECENT]
VECTORIZER = Vectorizer(r["headline"] for r in CORPUS)
STORIES = find_stories(TEXTS, SOURCES, VECTORIZER)


def index_of(fragment: str) -> int:
    matches = [i for i, t in enumerate(TEXTS) if fragment in t]
    assert len(matches) == 1, (fragment, matches)
    return matches[0]


def story_containing(i: int) -> set[int]:
    return next((set(s) for s in STORIES if i in s), set())


def test_char_ngrams_ignore_zwj_and_punctuation():
    assert char_ngrams("ශ්‍රී ලංකා!") == char_ngrams("ශ්රී  ලංකා")


def test_cosine_of_identical_text_is_one():
    v = VECTORIZER.transform(TEXTS[0])
    assert abs(cosine(v, v) - 1) < 1e-9


def test_riyadh_airport_attack_is_the_most_covered_story():
    top = STORIES[0]
    assert index_of("රියාද් ගුවන්තොටුපොළට ප්‍රහාරයක්") in top
    assert {SOURCES[i] for i in top} >= {"ada", "nethnews", "lankadeepa"}


@pytest.mark.parametrize(
    "fragments",
    [
        # Aswesuma payments taken dishonestly: three publishers, three wordings
        ["අස්වැසුම මුදල් හොරෙන්", "අපි අස්වැසුම හොරෙන්", "අස්වැසුම හොරා කැවැයි"],
        # Mahinda Rajapaksa taken to hospital
        ["මහින්ද රෝහල් ගත කරයි", "මහින්ද හදිසියේ රෝහල් ගත"],
        # Oil tanker fire near Hormuz (හෝමූස් / හෝමුස් spelt differently)
        ["හෝමූස් පසු කරන්න", "හෝමුස් අසලදී"],
        # Floods in Nepal
        ["නේපාලයේ හදිසි ගංවතුරෙන්", "නේපාලයේ ප්‍රධාන ගංගාවක"],
    ],
)
def test_same_story_from_different_publishers_is_grouped(fragments):
    ids = [index_of(f) for f in fragments]
    assert set(ids) <= story_containing(ids[0])


def test_every_story_has_at_least_two_publishers():
    for s in STORIES:
        assert len({SOURCES[i] for i in s}) >= 2


def test_same_publisher_alone_never_forms_a_story():
    # Siyatha's two headlines on the Sri Lanka v Pakistan series are not grouped by themselves
    texts = ["ශ්‍රී ලංකා – පාකිස්ථාන විස්සයි විස්ස තරගාවලිය අදින් ඇරඹෙයි", "ශ්‍රී ලංකා – පාකිස්ථාන විස්සයි විස්ස පළමු තරගය අද"]
    assert find_stories(texts, ["siyatha", "siyatha"], VECTORIZER) == []


def test_unrelated_headlines_stay_apart():
    assert story_containing(index_of("උතුරු දුම්රිය මාර්ගයේ දෛනික ගමන්වාර")) == set()
    assert story_containing(index_of("තුර්කියේ දරුවන්ට සමාජ මාධ්‍ය තහනම්")) == set()


def test_stories_are_ranked_by_publisher_count():
    counts = [len({SOURCES[i] for i in s}) for s in STORIES]
    assert counts == sorted(counts, reverse=True)
