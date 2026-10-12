"""Statistics for exploring the corpus. Pure functions over a pandas DataFrame,
so the notebook stays short and every number in it is tested.

Load with ``load_corpus()``; every other function takes that DataFrame.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter
from datetime import timedelta, timezone
from pathlib import Path

import pandas as pd

from collector.categories import LABELS
from collector.storage import month_files
from collector.stories import Vectorizer, find_stories

SRI_LANKA_TZ = timezone(timedelta(hours=5, minutes=30))

# Sinhala letters with the ZWJ (so ශ්‍රී stays one word), or runs of Latin letters.
_WORD_RE = re.compile(r"[඀-෿‍]+|[A-Za-z]+")

# A small hand-made list of function words and very common verbs/particles.
# Good enough to make the frequency tables informative; not a linguistic resource.
STOPWORDS = frozenset(
    """
    සහ හා ද ය යි ක් වූ වන වී වෙයි වේ කළ කරයි කරන කෙරේ කර කරන්න ගැන සඳහා බව සමග සමඟ දක්වා වෙත
    පමණ නිසා අද නව තවත් එක් ලෙස ඇති නැති විසින් අතර පසු මත තුළ සිට දී දෙයි ගනී යයි එයි
    මෙම එම ඒ මේ නොවේ නෑ බැ බෑ යළි යළිත් ලබයි ලැබූ දෙන ගත් ගත ඇතුළු පිළිබඳ කියයි
    """.split()
)


def load_corpus(data_dir: str | Path = "data/raw") -> pd.DataFrame:
    """All monthly CSVs as one DataFrame, with a few derived columns."""
    rows = []
    for path in month_files(data_dir):
        with open(path, encoding="utf-8", newline="") as fh:
            rows.extend(csv.DictReader(fh))
    df = pd.DataFrame(rows, columns=["date", "source", "headline", "category", "url", "collected_at"])
    df["date"] = pd.to_datetime(df["date"])
    df["collected_at"] = pd.to_datetime(df["collected_at"], utc=True)
    df["collected_day"] = df["collected_at"].dt.tz_convert(SRI_LANKA_TZ).dt.date
    df["chars"] = df["headline"].str.replace("‍", "", regex=False).str.len()
    df["words"] = df["headline"].map(lambda h: len(tokenize(h, keep_stopwords=True)))
    return df


def tokenize(headline: str, keep_stopwords: bool = False) -> list[str]:
    """Words of a cleaned headline. English words are lower-cased; numbers dropped."""
    words = [w.lower() for w in _WORD_RE.findall(headline)]
    words = [w.strip("‍") for w in words]
    return [w for w in words if w and (keep_stopwords or w not in STOPWORDS)]


def label_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Headlines per label (all labels, including empty ones), with shares."""
    counts = df["category"].value_counts().reindex(list(LABELS), fill_value=0)
    out = counts.rename("headlines").to_frame()
    out["share"] = (out["headlines"] / max(1, len(df))).round(3)
    return out


def source_label_table(df: pd.DataFrame) -> pd.DataFrame:
    """Sources x labels count table, with every label as a column."""
    table = pd.crosstab(df["source"], df["category"]).reindex(columns=list(LABELS), fill_value=0)
    table["total"] = table.sum(axis=1)
    return table.sort_values("total", ascending=False)


def length_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Headline length in characters and words, per label and overall."""
    def summary(frame: pd.DataFrame) -> dict:
        return {
            "headlines": len(frame),
            "chars_median": frame["chars"].median(),
            "chars_p90": frame["chars"].quantile(0.9),
            "words_median": frame["words"].median(),
            "words_p90": frame["words"].quantile(0.9),
        }

    rows = {label: summary(group) for label, group in df.groupby("category") if len(group)}
    rows["all"] = summary(df)
    return pd.DataFrame(rows).T


def top_terms(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Most frequent words, stopwords removed. Counted once per headline."""
    counts = Counter(w for h in df["headline"] for w in set(tokenize(h)))
    return pd.DataFrame(counts.most_common(n), columns=["word", "headlines"])


def distinctive_terms(df: pd.DataFrame, label: str, n: int = 10, min_count: int = 3) -> pd.DataFrame:
    """Words most typical of one label versus all the others.

    Score: smoothed log-ratio of the share of headlines containing the word in
    this label versus in the rest. Rare words (< min_count in the label) are skipped.
    """
    inside = df[df["category"] == label]["headline"]
    outside = df[df["category"] != label]["headline"]
    cin = Counter(w for h in inside for w in set(tokenize(h)))
    cout = Counter(w for h in outside for w in set(tokenize(h)))
    rows = []
    for word, k in cin.items():
        if k < min_count:
            continue
        p_in = (k + 0.5) / (len(inside) + 1)
        p_out = (cout.get(word, 0) + 0.5) / (len(outside) + 1)
        rows.append((word, k, cout.get(word, 0), math.log(p_in / p_out)))
    out = pd.DataFrame(rows, columns=["word", f"in_{label}", "elsewhere", "score"])
    return out.sort_values(["score", f"in_{label}"], ascending=False).head(n).reset_index(drop=True)


def daily_volume(df: pd.DataFrame) -> pd.DataFrame:
    """New headlines added per collection day (Sri Lanka time), per source."""
    return pd.crosstab(df["collected_day"], df["source"]).assign(total=lambda t: t.sum(axis=1))


def cross_publisher_stories(df: pd.DataFrame) -> pd.DataFrame:
    """Stories covered by several publishers, found day by day.

    Uses the same grouping as the website (collector.stories), with IDF learned
    from the whole corpus. One row per story.
    """
    vectorizer = Vectorizer(df["headline"])
    rows = []
    for day, group in df.groupby(df["date"].dt.date):
        group = group.reset_index(drop=True)
        for story in find_stories(group["headline"].tolist(), group["source"].tolist(), vectorizer):
            members = group.iloc[story]
            rows.append(
                {
                    "date": day,
                    "publishers": members["source"].nunique(),
                    "headlines": len(members),
                    "labels": sorted(set(members["category"])),
                    "same_label": members["category"].nunique() == 1,
                    "example": members.iloc[0]["headline"],
                }
            )
    return pd.DataFrame(rows, columns=["date", "publishers", "headlines", "labels", "same_label", "example"])


def label_agreement(stories: pd.DataFrame, min_publishers: int = 2) -> float:
    """Share of multi-publisher stories that every publisher filed under the same label."""
    eligible = stories[stories["publishers"] >= min_publishers]
    return float(eligible["same_label"].mean()) if len(eligible) else float("nan")
