import math

import pandas as pd
import pytest

from analysis import eda
from collector.storage import append_rows


def _rows():
    def r(i, day, source, category, headline):
        return {
            "date": day,
            "source": source,
            "headline": headline,
            "category": category,
            "url": f"https://example.lk/{i}",
            "collected_at": f"{day}T01:00:00Z",
        }

    return [
        r(1, "2026-10-12", "lankadeepa", "local", "මහින්ද රෝහල් ගත කරයි"),
        r(2, "2026-10-12", "nethnews", "politics", "හිටපු ජනපති මහින්ද හදිසියේ රෝහල් ගත කෙරේ"),
        r(3, "2026-10-12", "ada", "sports", "ශ්‍රී ලංකා කණ්ඩායමට ජය"),
        r(4, "2026-10-11", "ada", "sports", "ශ්‍රී ලංකා - පාකිස්ථාන තරගය අද"),
        r(5, "2026-10-11", "siyatha", "sports", "ක්‍රිකට් තරගය අද ආරම්භ වේ"),
        r(6, "2026-10-11", "lankatruth", "business", "IMF සහ රජය අතර සාකච්ඡා"),
    ]


@pytest.fixture
def df(tmp_path):
    append_rows(tmp_path, _rows())
    return eda.load_corpus(tmp_path)


def test_load_corpus_adds_lengths_and_days(df):
    assert len(df) == 6
    assert {"chars", "words", "collected_day"} <= set(df.columns)
    # ZWJ is not counted as a character
    assert df.loc[df["headline"].str.startswith("ශ්‍රී ලංකා කණ්ඩායමට"), "chars"].item() == len("ශ්රී ලංකා කණ්ඩායමට ජය")


def test_tokenize_keeps_conjuncts_and_drops_stopwords():
    assert eda.tokenize("ශ්‍රී ලංකා සහ IMF සාකච්ඡා 2026") == ["ශ්‍රී", "ලංකා", "imf", "සාකච්ඡා"]
    assert "සහ" in eda.tokenize("ශ්‍රී ලංකා සහ IMF", keep_stopwords=True)


def test_label_balance_lists_every_label(df):
    balance = eda.label_balance(df)
    assert list(balance.index)[:3] == ["politics", "business", "sports"]
    assert balance.loc["sports", "headlines"] == 3
    assert balance.loc["entertainment", "headlines"] == 0
    assert balance["headlines"].sum() == 6


def test_source_label_table(df):
    table = eda.source_label_table(df)
    assert table.loc["ada", "sports"] == 2
    assert table.loc["ada", "total"] == 2
    assert "technology" in table.columns


def test_length_summary_has_overall_row(df):
    summary = eda.length_summary(df)
    assert summary.loc["all", "headlines"] == 6
    assert summary.loc["sports", "headlines"] == 3


def test_top_terms_counts_once_per_headline(df):
    terms = eda.top_terms(df).set_index("word")["headlines"]
    assert terms["තරගය"] == 2
    assert "අද" not in terms  # stopword


def test_distinctive_terms_for_sports(df):
    top = eda.distinctive_terms(df, "sports", min_count=2)
    assert top.iloc[0]["word"] in {"තරගය", "ශ්‍රී", "ලංකා"}


def test_daily_volume(df):
    volume = eda.daily_volume(df)
    assert volume["total"].sum() == 6
    assert len(volume) == 2


def test_cross_publisher_stories_and_label_agreement(df):
    stories = eda.cross_publisher_stories(df)
    mahinda = stories[stories["example"].str.contains("මහින්ද")]
    assert len(mahinda) == 1
    assert mahinda.iloc[0]["publishers"] == 2
    assert not mahinda.iloc[0]["same_label"]  # filed as local by one, politics by the other
    assert eda.label_agreement(stories) == 0.0


def test_label_agreement_empty_is_nan():
    empty = pd.DataFrame(columns=["publishers", "same_label"])
    assert math.isnan(eda.label_agreement(empty))
