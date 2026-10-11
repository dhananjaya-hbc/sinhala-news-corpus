"""Map each site's own category names onto the corpus label set."""

from __future__ import annotations

import html
import unicodedata
from collections.abc import Iterable, Mapping

from collector.sinhala_text import collapse_whitespace

LABELS = (
    "politics",
    "business",
    "sports",
    "international",
    "entertainment",
    "technology",
    "local",
    "other",
)

# Feeds often attach several categories to one item (e.g. Dinamina tags an
# IMF meeting abroad with both දේශපාලන "politics" and විදෙස් "foreign").
# The most specific topic wins; "local" and "other" are catch-alls.
PRIORITY = (
    "sports",
    "entertainment",
    "technology",
    "business",
    "international",
    "politics",
    "local",
    "other",
)

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def normalize_term(term: str) -> str:
    """Comparison form of a site category: NFC, no zero-width chars, casefolded.

    Divaina's sports category, for example, is "ක්‍රී​ඩා" with a stray U+200B
    inside; it must still match a mapping written as "ක්‍රීඩා".
    """
    term = unicodedata.normalize("NFC", html.unescape(term)).translate(_ZERO_WIDTH)
    return collapse_whitespace(term).casefold()


def build_category_map(raw: Mapping[str, str]) -> dict[str, str]:
    """Validate a source's ``category_map`` and normalise its keys."""
    mapping = {}
    for term, label in raw.items():
        if label not in LABELS:
            raise ValueError(f"category {term!r} maps to unknown label {label!r}")
        mapping[normalize_term(term)] = label
    return mapping


def pick_category(terms: Iterable[str], category_map: Mapping[str, str], default: str = "other") -> str:
    """Return the highest-priority label among ``terms``, else ``default``.

    ``category_map`` must come from ``build_category_map``. Terms without a
    mapping (free-form tags like "Donald Trump") are ignored.
    """
    if default not in LABELS:
        raise ValueError(f"unknown default label {default!r}")
    found = {category_map[key] for key in map(normalize_term, terms) if key in category_map}
    for label in PRIORITY:
        if label in found:
            return label
    return default
