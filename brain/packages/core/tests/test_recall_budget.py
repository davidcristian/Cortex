import pytest

from cortex_core import cut_marker, fit_recalled, recall_allowances


def test_texts_that_fit_together_keep_their_lengths() -> None:
    assert recall_allowances([10, 20, 30], 60) == [10, 20, 30]


def test_what_a_short_text_leaves_is_shared_by_the_longer_ones() -> None:
    assert recall_allowances([10_000, 100, 10_000], 6000) == [2950, 100, 2950]


def test_one_long_text_may_fill_the_whole_budget() -> None:
    assert recall_allowances([12_000], 6000) == [6000]


def test_an_uneven_split_hands_the_remainder_to_the_last_text() -> None:
    assert recall_allowances([5, 5, 5], 10) == [3, 3, 4]


def test_no_texts_need_no_allowance() -> None:
    assert recall_allowances([], 6000) == []


@pytest.mark.parametrize(
    "lengths",
    [[9000] * 5, [1, 2, 3, 50_000, 7], [6000, 6000], [0, 0, 12_001], [5999, 1]],
)
def test_the_allowances_never_sum_past_the_budget(lengths: list[int]) -> None:
    allowances = recall_allowances(lengths, 6000)
    assert sum(allowances) <= 6000
    assert all(0 <= share <= length for share, length in zip(allowances, lengths, strict=True))


def test_a_text_within_its_allowance_is_shown_whole() -> None:
    assert fit_recalled(["tea", "coffee"], 9) == ["tea", "coffee"]


def test_a_text_past_its_allowance_is_cut_with_a_marker_naming_what_is_left_out() -> None:
    assert fit_recalled(["abcdefgh"], 3) == ["abc\n[memory cut here: 5 more characters not shown]"]


def test_the_marker_names_the_hidden_count() -> None:
    assert cut_marker(12) == "\n[memory cut here: 12 more characters not shown]"


def test_the_shipped_budget_shows_five_long_memories_1200_characters_each() -> None:
    assert fit_recalled(["x" * 20_000] * 5) == ["x" * 1200 + cut_marker(18_800)] * 5
