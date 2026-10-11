import pytest

from collector.categories import LABELS, PRIORITY, build_category_map, normalize_term, pick_category

DINAMINA = build_category_map(
    {
        "දේශීය පුවත්": "local",
        "විදෙස්": "international",
        "ක්‍රීඩා": "sports",
        "දේශපාලන": "politics",
        "ව්‍යාපාරික": "business",
    }
)


def test_priority_covers_every_label():
    assert sorted(PRIORITY) == sorted(LABELS)


def test_single_tag_maps():
    assert pick_category(["ක්‍රීඩා"], DINAMINA) == "sports"


def test_specific_label_beats_local():
    # real Dinamina item: උණුසුම් පුවත් (hot news), දේශපාලන, දේශීය පුවත්
    assert pick_category(["උණුසුම් පුවත්", "දවසේ පුවත්", "දේශපාලන", "දේශීය පුවත්"], DINAMINA) == "politics"


def test_international_beats_politics():
    # real Dinamina item about an IMF meeting in Thailand
    assert pick_category(["උණුසුම් පුවත්", "දේශපාලන", "විදෙස්"], DINAMINA) == "international"


def test_unmapped_tags_fall_back_to_default():
    assert pick_category(["උණුසුම් පුවත්", "Donald Trump"], DINAMINA) == "other"
    assert pick_category([], DINAMINA, default="local") == "local"


def test_zero_width_space_inside_site_category_still_matches():
    # Divaina's real sports category name has a U+200B: "ක්‍රී​ඩා"
    assert pick_category(["ක්‍රී​ඩා"], DINAMINA) == "sports"


def test_english_terms_are_case_insensitive_and_entities_decoded():
    mapping = build_category_map({"Crime & Law": "local", "Foreign News": "international"})
    assert pick_category(["crime &amp; law"], mapping) == "local"
    assert pick_category(["FOREIGN  NEWS"], mapping) == "international"


def test_normalize_term_strips_zwj():
    assert normalize_term("ව්‍යාපාරික") == normalize_term("ව්යාපාරික")


def test_unknown_label_rejected():
    with pytest.raises(ValueError):
        build_category_map({"කාටූන්": "cartoons"})
    with pytest.raises(ValueError):
        pick_category([], DINAMINA, default="news")
