from pathlib import Path

import pytest

import trailwidth

# What the process wrote, and what reading the log back put in front of it. The second is the
# compose service prefix, which never crossed the driver and is therefore no part of any width.
RECORD = "INFO:cortex.memory.recall:memory.recall"
CAPTURED = "brain-1  | "
PREFIX = f"{CAPTURED}{RECORD}"


def trail(dropped: str, *, after: str = " dropped_omitted=0 k=5") -> str:
    """One rendered trail line with ``dropped`` carrying the given rendering."""
    return f"{PREFIX} basis=verdict dropped={dropped}{after}"


def whole(line: str) -> int:
    """The width the line above renders at, which is everything the capture's prefix is not."""
    return len(line) - len(CAPTURED)


def capture(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_read_line_measures_the_rendering_between_the_field_and_the_next_one() -> None:
    line = trail('[{"id":"a","score":0.5}]')
    assert trailwidth.read_line(line) == trailwidth.Reading(24, whole(line), 1, cut=False)


def test_read_line_reads_a_field_that_ends_the_line() -> None:
    line = trail("[]", after="")
    assert trailwidth.read_line(line) == trailwidth.Reading(2, whole(line), 0, cut=False)


def test_read_line_measures_the_line_from_where_the_formatter_starts() -> None:
    """A capture read back through `docker compose logs` opens every line with a prefix the
    process never wrote, so counting the file's own characters would measure the reader of the
    log rather than the line, and the two captures this harness takes carry different ones."""
    plain = f"{RECORD} basis=verdict dropped=[] k=5"
    assert trailwidth.read_line(plain) == trailwidth.Reading(2, len(plain), 0, cut=False)
    assert trailwidth.read_line(f"{CAPTURED}{plain}") == trailwidth.read_line(plain)


def test_read_line_ignores_a_line_that_is_not_the_trail() -> None:
    assert trailwidth.read_line("INFO:cortex.turn:turn.done dropped=[1,2] k=5") is None


def test_read_line_ignores_a_line_whose_message_only_resembles_the_trails() -> None:
    """The sink logs through `cortex.memory.recall`, so this word sits on every line it writes,
    message or not. A needle matched anywhere in the line would read a sibling line as a trail
    line and measure a field that belongs to something else."""
    assert trailwidth.read_line("INFO:cortex.memory.recall:memory.forgone dropped=[] k=5") is None


def test_read_line_ignores_a_message_the_trails_own_is_the_opening_of() -> None:
    """A message ends where the formatter puts a space, so a longer one starting with this one is
    a different line and not a trail line with something after it."""
    assert trailwidth.read_line("INFO:cortex.memory.recall:memory.recalled dropped=[]") is None


def test_read_line_ignores_a_trail_line_carrying_no_such_field() -> None:
    assert trailwidth.read_line(f"{PREFIX} basis=demur dropped_omitted=0 k=5") is None


def test_read_line_keeps_a_cut_markers_own_width_and_counts_no_candidates() -> None:
    rendering = '[{"id":"a"<cut 900 chars>'
    line = trail(rendering)
    assert trailwidth.read_line(line) == trailwidth.Reading(
        len(rendering), whole(line), None, cut=True
    )


def test_read_line_calls_a_marker_inside_the_value_no_cut_at_all() -> None:
    """A cut marker can only ever sit at the end, so one in the middle is the value's own text."""
    rendering = '[{"id":"a<cut 9 chars>b"}]'
    line = trail(rendering)
    assert trailwidth.read_line(line) == trailwidth.Reading(
        len(rendering), whole(line), 1, cut=False
    )


def test_read_line_counts_no_candidates_on_a_rendering_that_is_not_a_list() -> None:
    line = trail('{"id":"a"}')
    assert trailwidth.read_line(line) == trailwidth.Reading(10, whole(line), None, cut=False)


def test_read_line_counts_no_candidates_on_a_rendering_that_will_not_parse() -> None:
    line = trail("[oops")
    assert trailwidth.read_line(line) == trailwidth.Reading(5, whole(line), None, cut=False)


def test_readings_keeps_every_trail_line_in_the_captures_own_order() -> None:
    text = "\n".join([trail('[{"id":"a"}]'), "unrelated line", trail("[]")])
    assert [reading.width for reading in trailwidth.readings(text)] == [12, 2]


def test_load_reads_a_capture_into_a_block(tmp_path: Path) -> None:
    first, second = trail("[]"), trail('[{"id":"a"}]')
    block = trailwidth.load(capture(tmp_path / "b.log", first, second))
    assert block.path.name == "b.log"
    assert block.widths == (2, 12)
    assert block.lines == (whole(first), whole(second))
    assert block.cut == 0


def test_load_counts_the_renderings_the_bound_cut(tmp_path: Path) -> None:
    block = trailwidth.load(
        capture(tmp_path / "c.log", trail('[{"id":"a"<cut 9 chars>'), trail("[]"))
    )
    assert block.cut == 1


def test_load_refuses_a_file_it_cannot_read(tmp_path: Path) -> None:
    with pytest.raises(trailwidth.TrailWidthError, match="unreadable capture"):
        trailwidth.load(tmp_path / "missing.log")


def test_load_refuses_a_capture_holding_no_trail_line(tmp_path: Path) -> None:
    path = capture(tmp_path / "empty.log", "nothing here")
    with pytest.raises(trailwidth.TrailWidthError, match=r"no memory\.recall line"):
        trailwidth.load(path)


def test_shape_reports_the_count_floor_median_and_ceiling() -> None:
    assert trailwidth.shape([2, 12, 13]) == trailwidth.Shape(3, 2, 12.0, 13)


def test_by_entries_groups_readings_by_the_candidates_the_line_named(tmp_path: Path) -> None:
    block = trailwidth.load(
        capture(
            tmp_path / "g.log",
            trail('[{"id":"a"}]'),
            trail('[{"id":"ab"}]'),
            trail('[{"id":"a"},{"id":"b"}]'),
        )
    )
    grouped = trailwidth.by_entries([block])
    assert {entries: [read.width for read in cohort] for entries, cohort in grouped.items()} == {
        1: [12, 13],
        2: [23],
    }


def test_by_entries_leaves_out_a_rendering_with_no_candidate_count(tmp_path: Path) -> None:
    block = trailwidth.load(capture(tmp_path / "n.log", trail('[{"id":"a"<cut 9 chars>')))
    assert trailwidth.by_entries([block]) == {}


def test_report_names_each_block_its_range_and_the_overall_range(tmp_path: Path) -> None:
    first = trailwidth.load(capture(tmp_path / "one.log", trail("[]"), trail('[{"id":"a"}]')))
    second = trailwidth.load(capture(tmp_path / "two.log", trail('[{"id":"abc"}]')))
    text = trailwidth.report([first, second], resamples=50, seed=7)
    assert "blocks: 2, resamples: 50, seed: 7" in text
    assert "one.log (n=2): 2 to 12 chars" in text
    assert "two.log (n=1): 14 to 14 chars" in text
    assert "over all 3 trail lines: the field 2 to 14 chars" in text
    assert "cut by the bound: 0" in text


def test_report_names_each_blocks_whole_line_beside_its_field(tmp_path: Path) -> None:
    """The line is the reading the per-value bound leaves open, so it is printed per block in the
    same terms as the field, and it carries no interval: a mean's sampling distribution is not a
    statement about the ceiling this one is read for."""
    narrow, wide = trail("[]"), trail('[{"id":"a"}]')
    block = trailwidth.load(capture(tmp_path / "one.log", narrow, wide))
    text = trailwidth.report([block], resamples=50, seed=7)
    middle = (whole(narrow) + whole(wide)) / 2
    assert f"one.log (n=2): {whole(narrow)} to {whole(wide)} chars, median {middle:.1f}" in text
    # One interval per block and not two: the field's. Counted over the report rather than read
    # off the row, since what would be wrong is a second interval anywhere in it.
    assert text.count("95% CI") == 1


def test_report_pools_the_whole_line_over_every_block(tmp_path: Path) -> None:
    """The last two lines are what a reader opens the report for, so the pooled line sits there
    beside the pooled field rather than being left to be added up per block."""
    narrow, wide = trail("[]"), trail('[{"id":"a"}]')
    first = trailwidth.load(capture(tmp_path / "one.log", narrow))
    second = trailwidth.load(capture(tmp_path / "two.log", wide))
    text = trailwidth.report([first, second], resamples=50, seed=7)
    assert f"the whole line {whole(narrow)} to {whole(wide)}" in text


def test_report_reads_a_cohort_per_candidate(tmp_path: Path) -> None:
    block = trailwidth.load(capture(tmp_path / "p.log", trail('[{"id":"a"},{"id":"b"}]')))
    assert "2 dropped (n=   1): 23 to 23 chars" in trailwidth.report([block], resamples=50, seed=7)
    assert "11.50 to 11.50 per candidate" in trailwidth.report([block], resamples=50, seed=7)


def test_report_reads_a_cohort_against_the_lines_it_sat_on(tmp_path: Path) -> None:
    """The cohort's own row and not a pooled reading that happens to spell the same numbers: the
    whole line is grouped by the candidates the field named, which is the grouping that showed
    the widest field and the widest line are not the same line."""
    line = trail('[{"id":"a"},{"id":"b"}]')
    block = trailwidth.load(capture(tmp_path / "p.log", line))
    text = trailwidth.report([block], resamples=50, seed=7)
    row = f"per candidate, whole line {whole(line)} to {whole(line)}"
    assert row in text


def test_report_describes_the_empty_list_rather_than_dividing_by_it(tmp_path: Path) -> None:
    block = trailwidth.load(capture(tmp_path / "e.log", trail("[]")))
    assert "an empty list" in trailwidth.report([block], resamples=50, seed=7)


def test_report_counts_every_cut_rendering_across_the_blocks(tmp_path: Path) -> None:
    block = trailwidth.load(capture(tmp_path / "c.log", trail('[{"id":"a"<cut 9 chars>')))
    assert "cut by the bound: 1" in trailwidth.report([block], resamples=50, seed=7)


def test_main_prints_the_report_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = capture(tmp_path / "m.log", trail('[{"id":"a"}]'))
    assert trailwidth.main([str(path), "--resamples", "50", "--seed", "7"]) == 0
    assert "over all 1 trail lines: the field 12 to 12 chars" in capsys.readouterr().out


def test_main_refuses_a_capture_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert trailwidth.main([str(tmp_path / "missing.log")]) == 2
    assert "trailwidth: " in capsys.readouterr().err


def test_main_refuses_a_non_positive_resample_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = capture(tmp_path / "m.log", trail('[{"id":"a"}]'))
    assert trailwidth.main([str(path), "--resamples", "0"]) == 2
    assert "at least one resample" in capsys.readouterr().err
