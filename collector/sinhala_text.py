"""Cleaning helpers for Sinhala news headlines.

Each step is a small pure function so it can be tested on its own;
``clean_headline`` chains them in the order the collector needs.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Iterable

SINHALA_BLOCK = ("඀", "෿")
ZWJ = "‍"  # zero-width joiner
ZWNJ = "‌"  # zero-width non-joiner
AL_LAKUNA = "්"  # ් (hal kirima / virama)

# Invisible characters with no meaning in a headline. They break tokenisers
# and make identical headlines compare unequal. ZWJ is not in this list
# because in Sinhala it is meaningful (see ``fix_zwj``).
_INVISIBLE = dict.fromkeys(map(ord, "​⁠﻿­"), None)

_TAG_RE = re.compile(r"<[^<>]+>")
_WS_RE = re.compile(r"\s+")
_SUFFIX_SEP = r"\s*[-–—|:•]\s*"

DEFAULT_MIN_SINHALA_RATIO = 0.3


def is_sinhala(ch: str) -> bool:
    return SINHALA_BLOCK[0] <= ch <= SINHALA_BLOCK[1]


def is_sinhala_consonant(ch: str) -> bool:
    """True for the consonants ක (U+0D9A) .. ෆ (U+0DC6)."""
    return "ක" <= ch <= "ෆ"


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities.

    Runs twice because some feeds double-escape (``&amp;quot;``) or ship
    escaped markup (``&lt;b&gt;``) that only becomes a tag after one decode.
    """
    for _ in range(2):
        text = html.unescape(_TAG_RE.sub(" ", text))
    return text


def normalize_unicode(text: str) -> str:
    """NFC-normalise, e.g. ෙ + ා (two code points) -> ො (one)."""
    return unicodedata.normalize("NFC", text)


def remove_invisible(text: str) -> str:
    """Drop zero-width space, word joiner, BOM and soft hyphen."""
    return text.translate(_INVISIBLE)


def fix_zwj(text: str) -> str:
    """Keep ZWJ only where it builds a Sinhala ligature; drop the rest.

    Valid positions:
      * consonant + ් + ZWJ + consonant: yansaya (ය), rakaransaya (ර),
        repaya (ර්‍ය) and touching conjuncts such as ක්‍ෂ
      * consonant + ZWJ + ්: the older SLS 1134 form of touching letters

    Anything else (ZWJ after a vowel sign, next to a space, at the end of a
    word, doubled) is a stray character from copy/paste or a CMS and is removed.
    """
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch != ZWJ:
            out.append(ch)
            continue
        prev = out[-1] if out else ""
        prev2 = out[-2] if len(out) > 1 else ""
        nxt = next((c for c in text[i + 1 :] if c != ZWJ), "")
        if prev == AL_LAKUNA and is_sinhala_consonant(prev2) and is_sinhala_consonant(nxt):
            out.append(ch)
        elif is_sinhala_consonant(prev) and nxt == AL_LAKUNA:
            out.append(ch)
    return "".join(out)


def collapse_whitespace(text: str) -> str:
    """Turn any run of whitespace (incl. NBSP, tabs, newlines) into one space."""
    return _WS_RE.sub(" ", text).strip()


def strip_site_suffix(text: str, suffixes: Iterable[str]) -> str:
    """Remove a trailing ``" - Site Name"`` / ``" | Site Name"`` from a headline."""
    for suffix in suffixes:
        suffix = _normalize(suffix)
        if not suffix:
            continue
        pattern = re.compile(_SUFFIX_SEP + re.escape(suffix) + r"\s*$", re.IGNORECASE)
        text = pattern.sub("", text)
    return text.strip()


def sinhala_ratio(text: str) -> float:
    """Share of letters (incl. vowel signs) that are in the Sinhala block.

    Digits, punctuation and spaces are ignored so "2026 නොබෙල් ත්‍යාගය" scores
    1.0. Returns 0.0 when the text has no letters at all.
    """
    letters = [ch for ch in text if unicodedata.category(ch)[0] in "LM"]
    if not letters:
        return 0.0
    return sum(map(is_sinhala, letters)) / len(letters)


def is_legacy_font_text(text: str, min_ratio: float = DEFAULT_MIN_SINHALA_RATIO) -> bool:
    """Detect pre-Unicode Sinhala (FM Abhaya, DL-Manel, ...).

    Those fonts draw Sinhala glyphs on Latin code points, so in a Sinhala
    feed the text arrives as gibberish like ``Y%S ,xldj`` and scores ~0.
    Real Unicode headlines score near 1.0; even brand-heavy press releases
    ("Sumathi Information Technologies 25 වැනි සංවත්සරය සමරයි") stay above
    0.35, so the 0.3 default separates the two with a margin.
    """
    return sinhala_ratio(text) < min_ratio


def _normalize(text: str) -> str:
    text = normalize_unicode(text)
    text = remove_invisible(text)
    text = fix_zwj(text)
    text = collapse_whitespace(text)
    # Removing characters can leave a composable pair (ෙ + ා) behind.
    return normalize_unicode(text)


def clean_headline(raw: str, suffixes: Iterable[str] = ()) -> str:
    """Full pipeline: HTML -> NFC -> invisibles -> ZWJ -> whitespace -> suffix."""
    text = _normalize(strip_html(raw))
    return strip_site_suffix(text, suffixes)


def headline_key(text: str) -> str:
    """Comparison key for duplicate detection.

    Two headlines that differ only in punctuation, quotes, case of embedded
    English, spacing or ZWJ usage get the same key.
    """
    text = clean_headline(text).replace(ZWJ, "").replace(ZWNJ, "").casefold()
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] not in "PS")
    return collapse_whitespace(text)
