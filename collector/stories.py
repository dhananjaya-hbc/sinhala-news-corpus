"""Find headlines from different publishers that report the same story.

Sinhala words take many suffixes (තොටුපළට, තොටුපළකට, තොටුපොළවලට), so exact
word matching misses most pairs. Headlines are compared as TF-IDF weighted
character trigrams instead: rare names (අස්වැසුම, රියාද්) count for a lot,
common news words (අත්අඩංගුවට, අල්ලස්) for little. Pairs from different
publishers above a similarity threshold are linked, and linked headlines form
a story.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence

from collector.sinhala_text import headline_key

# Tuned on real data (October 2026): same-story pairs mostly score above 0.33,
# unrelated pairs that share a common phrase mostly score below it.
DEFAULT_THRESHOLD = 0.33

Vector = dict[str, float]


def char_ngrams(text: str, n: int = 3) -> Counter:
    """Character n-grams per word, with word boundaries marked by spaces."""
    grams: Counter = Counter()
    for word in headline_key(text).split():
        padded = f" {word} "
        grams.update(padded[i : i + n] for i in range(max(1, len(padded) - n + 1)))
    return grams


class Vectorizer:
    """TF-IDF over character n-grams; IDF is learned from a reference corpus."""

    def __init__(self, corpus: Iterable[str], n: int = 3):
        self.n = n
        df: Counter = Counter()
        size = 0
        for text in corpus:
            df.update(set(char_ngrams(text, n)))
            size += 1
        self._idf = {g: math.log((1 + size) / (1 + c)) + 1 for g, c in df.items()}
        self._unseen = math.log(1 + size) + 1  # n-grams not in the corpus are rare

    def transform(self, text: str) -> Vector:
        weights = {g: tf * self._idf.get(g, self._unseen) for g, tf in char_ngrams(text, self.n).items()}
        norm = math.sqrt(sum(w * w for w in weights.values()))
        return {g: w / norm for g, w in weights.items()} if norm else {}


def cosine(a: Vector, b: Vector) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(g, 0.0) for g, w in a.items())


def find_stories(
    headlines: Sequence[str],
    sources: Sequence[str],
    vectorizer: Vectorizer,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[list[int]]:
    """Group indices of headlines that report the same story.

    Only headlines from *different* publishers are linked, so a story is, by
    definition, covered by at least two sources. Each returned group lists its
    most representative headline first (the one most similar to the others).
    Groups are sorted by number of publishers, then size, then first index.
    """
    vectors = [vectorizer.transform(h) for h in headlines]
    parent = list(range(len(headlines)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    similar: dict[tuple[int, int], float] = {}
    for i in range(len(headlines)):
        for j in range(i + 1, len(headlines)):
            if sources[i] == sources[j]:
                continue
            score = cosine(vectors[i], vectors[j])
            if score >= threshold:
                similar[(i, j)] = score
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(len(headlines)):
        groups.setdefault(find(i), []).append(i)

    stories = []
    for members in groups.values():
        if len({sources[i] for i in members}) < 2:
            continue

        def centrality(i: int) -> float:
            return sum(cosine(vectors[i], vectors[j]) for j in members if j != i)

        stories.append(sorted(members, key=lambda i: (-centrality(i), i)))
    stories.sort(key=lambda s: (-len({sources[i] for i in s}), -len(s), min(s)))
    return stories
