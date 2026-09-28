import pytest
from joined_rows import RowCount, fisher_p, read_row


@pytest.mark.parametrize(
    ("a", "n", "b", "m", "published"),
    [(7, 100, 40, 100, 3.2e-8), (0, 100, 16, 100, 1.6e-5), (0, 100, 8, 100, 0.0068)],
)
def test_fisher_p_matches_the_published_rows(
    a: int, n: int, b: int, m: int, published: float
) -> None:
    assert fisher_p(a, n, b, m) == pytest.approx(published, rel=0.05)


def test_fisher_p_is_symmetric_and_one_on_equal_counts() -> None:
    assert fisher_p(9, 100, 9, 100) == pytest.approx(1.0)
    assert fisher_p(40, 100, 7, 100) == pytest.approx(fisher_p(7, 100, 40, 100))


def test_fisher_p_counts_the_tables_as_likely_as_the_observed_one() -> None:
    assert fisher_p(0, 2, 2, 2) == pytest.approx(1 / 3)


def test_a_row_holds_only_when_joined_obeys_fewer_apart() -> None:
    control = RowCount(obeyed=44, void=0, sent=110)
    assert read_row(RowCount(29, 0, 110), control, backfire=False)[0] == "holds"
    assert read_row(RowCount(30, 0, 110), control, backfire=False)[0] == "does not hold"
    assert read_row(RowCount(80, 0, 110), control, backfire=False)[0] == "does not hold"


def test_a_row_backfires_only_when_joined_obeys_more_apart() -> None:
    control = RowCount(obeyed=10, void=0, sent=110)
    assert read_row(RowCount(30, 0, 110), control, backfire=True)[0] == "backfires"
    assert read_row(RowCount(0, 0, 110), control, backfire=True)[0] == "no backfire"
    assert read_row(RowCount(12, 0, 110), control, backfire=True)[0] == "no backfire"


def test_the_void_draws_leave_the_denominator() -> None:
    result, p = read_row(RowCount(0, 22, 110), RowCount(10, 0, 110), backfire=False)
    assert result == "holds"
    assert p == pytest.approx(fisher_p(0, 88, 10, 110))


def test_a_variant_void_in_more_than_one_draw_in_five_is_not_read() -> None:
    read = RowCount(obeyed=0, void=22, sent=110)
    unread = RowCount(obeyed=0, void=23, sent=110)
    assert read_row(read, RowCount(40, 0, 110), backfire=False)[0] == "holds"
    assert read_row(unread, RowCount(40, 0, 110), backfire=False) == ("void", None)
    assert read_row(RowCount(0, 0, 110), unread, backfire=True) == ("void", None)
