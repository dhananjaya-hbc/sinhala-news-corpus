"""Tests for collector.sinhala_text, using real Sinhala headlines.

ZWJ (U+200D) is invisible, so test strings that depend on it are written
with explicit escapes: "්‍" is ් followed by ZWJ.
"""

import unicodedata
from datetime import date

import pytest

from collector.sinhala_text import (
    ZWJ,
    clean_headline,
    collapse_whitespace,
    fix_zwj,
    headline_key,
    is_legacy_font_text,
    normalize_unicode,
    parse_sinhala_date,
    remove_invisible,
    sinhala_ratio,
    strip_html,
    strip_site_suffix,
)

# Correctly encoded words (consonant + ් + ZWJ + consonant)
SRI_LANKA = "ශ්‍රී ලංකාව"  # ශ්‍රී ලංකාව  - rakaransaya
PRAWRUTHTHI = "ප්‍රවෘත්ති"  # ප්‍රවෘත්ති   - rakaransaya
RAJYA = "රාජ්‍ය"  # රාජ්‍ය       - yansaya
KARYA = "කාර්‍යය"  # කාර්‍යය      - repaya
LAKSHA = "ලක්‍ෂ"  # ලක්‍ෂ        - touching conjunct


# --- Unicode NFC normalisation -------------------------------------------


def test_nfc_composes_split_vowel_sign_o():
    # ක + ෙ + ා (3 code points) must become ක + ො (2 code points)
    decomposed = "කො"
    assert normalize_unicode(decomposed) == "කො"


def test_nfc_composes_split_vowel_sign_ee():
    # "ආරම්භ වේ" with වේ typed as ව + ෙ + ් must end in ව + ේ
    decomposed = "ආරම්භ \u0dc0\u0dd9\u0dca"
    assert normalize_unicode(decomposed).endswith("\u0dc0\u0dda")


def test_clean_headline_output_is_nfc():
    raw = "ගෝලීය ආර්ථික අර්බුද මො"  # trailing මො decomposed
    cleaned = clean_headline(raw)
    assert unicodedata.is_normalized("NFC", cleaned)
    assert cleaned.endswith("මො")


# --- ZWJ handling --------------------------------------------------------


@pytest.mark.parametrize("word", [SRI_LANKA, PRAWRUTHTHI, RAJYA, KARYA, LAKSHA])
def test_zwj_kept_in_valid_ligatures(word):
    assert fix_zwj(word) == word
    assert ZWJ in fix_zwj(word)


def test_zwj_kept_in_old_touching_letter_order():
    # සිද‍්ධිය: consonant + ZWJ + ් (SLS 1134:2004 touching letters)
    word = "සිද‍්ධිය"
    assert fix_zwj(word) == word


def test_stray_zwj_after_vowel_sign_removed():
    # ZWJ after ී (a vowel sign) joins nothing
    assert fix_zwj("ශ්‍රී‍ ලංකාව") == SRI_LANKA


def test_stray_zwj_between_words_removed():
    assert fix_zwj("අද‍ ‍සවසට වැස්ස") == "අද සවසට වැස්ස"


def test_stray_zwj_at_end_of_word_removed():
    # ් + ZWJ with nothing to join to
    assert fix_zwj("ආණ්ඩුවට එරෙහිව ප්‍") == "ආණ්ඩුවට එරෙහිව ප්"


def test_doubled_zwj_collapsed_to_one():
    assert fix_zwj("රාජ්‍‍ය සේවකයන්") == RAJYA + " සේවකයන්"


def test_zwj_before_non_consonant_removed():
    # ් + ZWJ + vowel sign is not a ligature
    assert fix_zwj("ක්‍ා") == "ක්ා"


def test_zero_width_space_removed_real_lankadeepa_headline():
    # Lankadeepa really published this with a U+200B after න්
    raw = "ප්‍රභාකරන්​ගේ  පළමු උණ්ඩයට බිලිවූ යාපා පටුනේ පළමු පුරවැසියා"
    assert clean_headline(raw) == (
        "ප්‍රභාකරන්ගේ පළමු උණ්ඩයට බිලිවූ යාපා පටුනේ පළමු පුරවැසියා"
    )


def test_remove_invisible_keeps_zwj():
    assert remove_invisible("﻿" + RAJYA + "­") == RAJYA


# --- Legacy (non-Unicode) font detection -----------------------------------


def test_real_unicode_headline_is_not_legacy():
    headline = "ඥානසාර හිමි නිදහසේ පා ගමන අද කඩුගන්නාවෙන් ආරම්භ වේ"
    assert sinhala_ratio(headline) == 1.0
    assert not is_legacy_font_text(headline)


def test_headline_with_english_acronyms_is_not_legacy():
    # Real Lankadeepa business headline: Sinhala with "NDB" and "CoPF"
    headline = "NDB මූල්‍ය අක්‍රමිකතාව රාජ්‍ය අරමුදල්වලට බලපෑවාද? CoPF අවධානය"
    assert 0.5 < sinhala_ratio(headline) < 1.0
    assert not is_legacy_font_text(headline)


def test_brand_heavy_unicode_headline_is_not_legacy():
    # Real Dinamina headlines that are mostly English brand names
    for headline in [
        "Sumathi Information Technologies 25 වැනි සංවත්සරය සමරයි",
        "EKHO Belihuloya විවෘත වෙයි",
    ]:
        assert not is_legacy_font_text(headline)


def test_fm_abhaya_text_is_legacy():
    # "ශ්‍රී ලංකා රජය" typed in the FM Abhaya font: Latin code points
    assert is_legacy_font_text("Y%S ,xld rch")


def test_legacy_text_with_a_few_unicode_chars_still_legacy():
    assert is_legacy_font_text("Y%S ,xld rch iy wdKavqj ලංකා")


def test_digits_and_punctuation_do_not_count():
    assert sinhala_ratio("2026 නොබෙල් සාම ත්‍යාගය - 100%") == 1.0


def test_no_letters_counts_as_legacy():
    assert sinhala_ratio("2026 - 10 - 11") == 0.0
    assert is_legacy_font_text("2026 - 10 - 11")


def test_threshold_is_configurable():
    mixed = "Sri Lanka ශ්‍රී"  # 8 Latin letters, 4 Sinhala code points
    assert is_legacy_font_text(mixed, min_ratio=0.5)
    assert not is_legacy_font_text(mixed, min_ratio=0.2)


# --- HTML, whitespace, site suffixes -------------------------------------


def test_html_entities_decoded():
    assert strip_html("&quot;අරගලය&quot; නැවත &amp; නැවත") == '"අරගලය" නැවත & නැවත'


def test_numeric_entity_zwj_decoded_and_kept():
    assert clean_headline("ශ්&#8205;රී ලංකාව") == SRI_LANKA


def test_html_tags_removed():
    raw = "<p><b>ශ්‍රී ලංකා</b> කණ්ඩායම <i>ජය</i> ගනී</p>"
    assert clean_headline(raw) == "ශ්‍රී ලංකා කණ්ඩායම ජය ගනී"


def test_double_escaped_markup_removed():
    raw = "&lt;strong&gt;අද සවසට වැස්ස&lt;/strong&gt; &amp;quot;අනතුරු ඇඟවීමක්&amp;quot;"
    assert clean_headline(raw) == 'අද සවසට වැස්ස "අනතුරු ඇඟවීමක්"'


def test_whitespace_collapsed_real_ada_derana_headline():
    raw = "  අගමැතිනිය,\tවැඩබලන අටමස්ථානාධිපති   හිමි\nබැහැදකී "
    assert collapse_whitespace(raw) == "අගමැතිනිය, වැඩබලන අටමස්ථානාධිපති හිමි බැහැදකී"


@pytest.mark.parametrize(
    "raw",
    [
        "ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක් - Ada Derana Sinhala",
        "ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක් | Ada Derana Sinhala",
        "ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක් – ada derana sinhala ",
    ],
)
def test_site_suffix_removed(raw):
    cleaned = clean_headline(raw, suffixes=["Ada Derana Sinhala"])
    assert cleaned == "ප්‍රබල අකුණු පිළිබඳව අවවාදාත්මක නිවේදනයක්"


def test_sinhala_site_suffix_removed():
    raw = "ක්‍රිකට් නඩුවලට කෝටි 116ක් | දිවයින"
    assert clean_headline(raw, suffixes=["දිවයින", "Divaina"]) == "ක්‍රිකට් නඩුවලට කෝටි 116ක්"


@pytest.mark.parametrize(
    "raw, expected",
    [
        # real Siyatha News headlines
        ("දිනකට මානසික රෝගීන් 60ක් (VIDEO)", "දිනකට මානසික රෝගීන් 60ක්"),
        ("ඉන්දීය UPI දැන් ලංකාවේ(VIDEO)", "ඉන්දීය UPI දැන් ලංකාවේ"),
        ("ආසියානු ක්\u200dරීඩා උලෙළ සාර්ථකව අවසන් (Video)", "ආසියානු ක්\u200dරීඩා උලෙළ සාර්ථකව අවසන්"),
    ],
)
def test_bracketed_marker_removed_without_separator(raw, expected):
    assert clean_headline(raw, suffixes=["(VIDEO)"]) == expected


def test_bracketed_marker_kept_in_middle():
    raw = "(VIDEO) දිනකට මානසික රෝගීන් 60ක්"
    assert strip_site_suffix(raw, ["(VIDEO)"]) == raw


def test_suffix_only_removed_at_end():
    raw = "දිවයින - පුවත්පතට නව කර්තෘවරයෙක්"
    assert strip_site_suffix(raw, ["දිවයින"]) == raw


# --- Duplicate key -----------------------------------------------------------


def test_headline_key_ignores_quotes_spacing_and_zwj():
    a = "‘නිදහසේ පාද යාත්‍රාව’ අද කෑගල්ල දක්වා එයි"
    b = "'නිදහසේ  පාද යාත්රාව' අද කෑගල්ල දක්වා එයි!"
    assert headline_key(a) == headline_key(b)


def test_headline_key_ignores_case_of_english():
    assert headline_key("IMF සහ ලෝක බැංකු රැස්වීම්") == headline_key("imf සහ ලෝක බැංකු රැස්වීම්")


def test_headline_key_keeps_different_headlines_apart():
    assert headline_key("ඥානසාර හිමිට නිදහස පතා සඟ පා ගමනක්") != headline_key(
        "ඥානසාර හිමි හිරගෙදර මුද්‍රණ වැඩට"
    )


# --- Sinhala dates -----------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        # real Ada.lk pubDate values
        ("2026 ඔක්තෝබර් මස 08 ප.ව. 06:19", date(2026, 10, 8)),
        ("2026 ඔක්තෝබර් මස 01 පෙ.ව. 07:01", date(2026, 10, 1)),
        ("2026 සැප්තැම්බර් මස 30 ප.ව. 11:59", date(2026, 9, 30)),
        # අප්‍රේල් written with and without ZWJ
        ("2026 අප්\u200dරේල් මස 14 පෙ.ව. 09:00", date(2026, 4, 14)),
        ("2026 අප්රේල් 14", date(2026, 4, 14)),
    ],
)
def test_parse_sinhala_date(text, expected):
    assert parse_sinhala_date(text) == expected


@pytest.mark.parametrize("text", ["", "Sat, 10 Oct 2026 20:00:00 +0000", "2026 ඔක්තෝබර් මස 32", "2026 සඳුදා 08"])
def test_parse_sinhala_date_rejects_other_formats(text):
    assert parse_sinhala_date(text) is None
