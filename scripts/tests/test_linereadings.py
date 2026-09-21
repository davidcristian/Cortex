from pathlib import Path

import pytest

import crosscheck
import linereadings
from needles import bounded


@pytest.mark.parametrize(
    ("needle", "line", "expected"),
    [
        ('"127.0.0.1:50051:50051"', '- "0.0.0.0:50051:50051"', ('"', ':50051:50051"', 3)),
        ('"127.0.0.1:50051:50051"', '- "127.0.0.1:6379:6379"', ('"127.0.0.1:', '"', 13)),
        (
            "host.docker.internal:50151",
            "1 host.docker.internal:50152 b",
            ("host.docker.internal:5015", "", 27),
        ),
        (
            "host.docker.internal:50151",
            "host.docker.internal:50152 b1",
            ("host.docker.internal:5015", "1", 25),
        ),
        ("abcdef", "xx Zbcdef", ("", "bcdef", 9)),
        ("10 s", "in **10.09 s**", ("10", " s", 7)),
        ("abc", "xyz", ("", "", 0)),
        ("x", "box", ("x", "", 3)),
        ("ab", "cb", ("", "b", 2)),
    ],
)
def test_a_line_is_credited_with_its_opening_and_then_its_closing_run(
    needle: str, line: str, expected: tuple[str, str, int]
) -> None:
    assert linereadings.split(needle, line) == expected


def test_the_two_runs_never_cover_more_than_the_needle() -> None:
    opening, closing, _ = linereadings.split("abcabc", "abcab abc")
    assert (opening, closing) == ("abcab", "c")
    assert len(opening) + len(closing) <= len("abcabc")


def test_a_tie_between_two_splits_keeps_the_longer_opening() -> None:
    assert linereadings.split("ab", "b a") == ("a", "", 3)


def _runs(needle: str, text: str) -> list[linereadings.LineRun] | None:
    return linereadings.line_runs(needle, text, bounded(needle))


def test_the_best_line_is_the_one_carrying_most_of_the_needle() -> None:
    text = '- "0.0.0.0:50051:50051"\n\n- "127.0.0.1:6379:6379"\n'
    (run,) = _runs('"127.0.0.1:50051:50051"', text) or []
    assert (run.number, run.length, run.column) == (1, 14, 3)
    assert run.stop == 3


def test_a_stop_is_an_offset_into_the_whole_text() -> None:
    (run,) = _runs("abcdef", "one\ntwo\nxx abcdeZ\n") or []
    assert (run.number, run.column, run.stop) == (3, 8, 16)


def test_lines_tied_for_the_most_are_all_returned_in_file_order() -> None:
    runs = _runs("abcdef", "abcdeX\nnothing\nabcdeY\n") or []
    assert [run.number for run in runs] == [1, 3]
    assert {run.length for run in runs} == {5}


def test_a_needle_absent_from_every_line_names_none() -> None:
    assert _runs("abcdef", "one\ntwo\n") == []


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("abcXXX\n", True),
        ("abXXXX\n", False),
    ],
)
def test_a_line_is_named_only_when_it_carries_at_least_half(text: str, *, named: bool) -> None:
    assert bool(_runs("abcdef", text)) is named


def test_a_needle_holding_a_newline_has_no_line_to_be_read_on() -> None:
    assert _runs("ab\ncd", "ab\ncX\n") is None


def test_a_found_occurrence_is_blanked_before_its_line_is_read() -> None:
    (run,) = _runs("port:50151", "port:50151 port:50152\nport:5\n") or []
    assert (run.number, run.opening, run.column) == (1, "port:5015", 20)


def test_a_line_whose_only_occurrence_was_found_carries_nothing_of_it() -> None:
    (run,) = _runs("port:50151", "port:50151\nport:50\n") or []
    assert run.number == 2


def test_a_single_best_line_is_named_with_its_share_and_its_words() -> None:
    needle = '"127.0.0.1:50051:50051"'
    runs = _runs(needle, '      - "0.0.0.0:50051:50051"\n') or []
    assert linereadings.said(runs, needle, None) == (
        "with the most of it on line 1, 14 of its 23 characters (its opening '\"' and its "
        "closing ':50051:50051\"'), where it reads '- \"0.0.0.0:50051:50051\"'"
    )


def test_tied_lines_are_counted_and_the_first_named_without_a_pairing() -> None:
    runs = _runs("abcdef", "abcdeX\nabcdeY\n") or []
    assert linereadings.said(runs, "abcdef", None) == (
        "with the most of it on 2 lines, 5 of its 6 characters (its opening 'abcde') each, "
        "the first on line 1, where it reads 'abcdeX'"
    )


def test_tied_lines_name_the_one_another_reading_was_paired_with() -> None:
    runs = _runs("abcdef", "abcdeX\nZbcdef\n") or []
    said = linereadings.said(runs, "abcdef", runs[1].stop)
    assert "(its closing 'bcdef') each, the nearest to that form on line 2" in said
    assert "where it reads 'Zbcdef'" in said


def test_no_line_carrying_half_is_said_as_such() -> None:
    assert linereadings.said([], "abcdef", None) == "with less than half of it on any line"


def test_a_long_line_is_quoted_around_the_run_it_carries() -> None:
    line = f"{'w' * 300} abcdeX {'x' * 300}"
    (run,) = _runs("abcdef", line) or []
    said = linereadings.said([run], "abcdef", None)
    assert f"where it reads '{linereadings.TRIMMED}" in said
    assert "abcdeX" in said
    assert said.endswith(f"{linereadings.TRIMMED}'")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a\nport\n", " (on line 2)"),
        ("port\nport\nb\nport\n", " (on lines 1, 2 and 4)"),
        ("port\n\nport\n", " (on lines 1 and 3)"),
    ],
)
def test_a_count_names_the_lines_it_found(text: str, expected: str) -> None:
    matches = list(bounded("port").finditer(text))
    assert linereadings.counted(text, matches) == expected


def test_a_short_count_over_a_needle_holding_a_newline_says_nothing_more() -> None:
    assert linereadings.short("ab\ncd", "ab\ncd\nab\ncX\n", bounded("ab\ncd")) == ""


_SEAM = crosscheck.Constant(
    label="a port",
    why="the stack publishes what the server binds",
    sites=(crosscheck.Site("config.py", "PORT"),),
    mentions=(crosscheck.Mention("stack.yml", '"127.0.0.1:{value}:{value}"'),),
)


def test_a_moved_interface_is_read_on_its_own_line_and_not_on_a_sibling(tmp_path: Path) -> None:
    (tmp_path / "config.py").write_text("PORT = 50051\n", encoding="utf-8")
    (tmp_path / "stack.yml").write_text(
        '    ports:\n      - "0.0.0.0:50051:50051"\n\n    ports:\n      - "127.0.0.1:6379:6379"\n',
        encoding="utf-8",
    )
    (fault,) = crosscheck.check_constant(tmp_path, _SEAM)
    assert "with the most of it on line 2, 14 of its 23 characters" in fault.detail
    assert "line 5" not in fault.detail
    assert "so what moved is likely shape this search text has" in fault.detail


_ENDPOINT = crosscheck.Constant(
    label="the body's own listen port",
    why="the container dials the port the host body binds",
    sites=(crosscheck.Site("config.py", "PORT"),),
    mentions=(crosscheck.Mention("runbook.md", "host.docker.internal:{value}", occurrences=2),),
)

_RUNBOOK = (
    "The brain dials `host.docker.internal:50151` by default.\n"
    "\n"
    "Reach the host as host.docker.internal: from a bridge container.\n"
    "\n"
    "    CORTEX_BODY_ENDPOINT=host.docker.internal:50151 just brain-serve\n"
)


def _runbook(root: Path, runbook: str) -> None:
    (root / "config.py").write_text("PORT = 50151\n", encoding="utf-8")
    (root / "runbook.md").write_text(runbook, encoding="utf-8")


def test_a_half_applied_rename_names_the_line_it_left(tmp_path: Path) -> None:
    _runbook(tmp_path, _RUNBOOK.replace(":50151 just", ":50152 just"))
    (fault,) = crosscheck.check_constant(tmp_path, _ENDPOINT)
    assert (
        "found 1 (on line 1), set to 2; outside those, the file is with the most of it on "
        "line 5, 25 of its 26 characters"
    ) in fault.detail
    assert "on line 5, 25 of its 26 characters (its opening 'host.docker.internal:5015')" in (
        fault.detail
    )
    assert "where it reads 'CORTEX_BODY_ENDPOINT=host.docker.internal:50152 just brain-serve'" in (
        fault.detail
    )


def test_a_deleted_occurrence_is_read_on_what_is_left_and_quoted(tmp_path: Path) -> None:
    _runbook(tmp_path, _RUNBOOK.replace("    CORTEX_BODY_ENDPOINT=host.docker.internal:50151", ""))
    (fault,) = crosscheck.check_constant(tmp_path, _ENDPOINT)
    assert "found 1 (on line 1), set to 2" in fault.detail
    assert "on line 3, 21 of its 26 characters (its opening 'host.docker.internal:')" in (
        fault.detail
    )
    assert "where it reads 'Reach the host as host.docker.internal: from a bridge container.'" in (
        fault.detail
    )


def test_a_deleted_occurrence_with_nothing_like_it_left_names_no_line(tmp_path: Path) -> None:
    _runbook(tmp_path, "The brain dials `host.docker.internal:50151`.\n\nSee the host.\n")
    (fault,) = crosscheck.check_constant(tmp_path, _ENDPOINT)
    assert (
        "found 1 (on line 1), set to 2; outside those, the file is with less than half of it "
        "on any line; move the whole set"
    ) in fault.detail
