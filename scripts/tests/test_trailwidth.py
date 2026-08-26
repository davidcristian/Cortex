from pathlib import Path

import pytest

import trailwidth

PREFIX = "brain-1  | INFO:cortex.memory.recall:memory.recall"


def trail(dropped: str, *, after: str = " dropped_omitted=0 k=5") -> str:
    """One rendered trail line with ``dropped`` carrying the given rendering."""
    return f"{PREFIX} basis=verdict dropped={dropped}{after}"


def capture(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_read_line_measures_the_rendering_between_the_field_and_the_next_one() -> None:
    assert trailwidth.read_line(trail('[{"id":"a","score":0.5}]')) == trailwidth.Reading(
        24, 1, cut=False
    )


def test_read_line_reads_a_field_that_ends_the_line() -> None:
    assert trailwidth.read_line(trail("[]", after="")) == trailwidth.Reading(2, 0, cut=False)


def test_read_line_ignores_a_line_that_is_not_the_trail() -> None:
    assert trailwidth.read_line("INFO:cortex.turn:turn.done dropped=[1,2] k=5") is None


def test_read_line_ignores_a_trail_line_carrying_no_such_field() -> None:
    assert trailwidth.read_line(f"{PREFIX} basis=demur dropped_omitted=0 k=5") is None


def test_read_line_keeps_a_cut_markers_own_width_and_counts_no_candidates() -> None:
    rendering = '[{"id":"a"<cut 900 chars>'
    assert trailwidth.read_line(trail(rendering)) == trailwidth.Reading(
        len(rendering), None, cut=True
    )


def test_read_line_calls_a_marker_inside_the_value_no_cut_at_all() -> None:
    """A cut marker can only ever sit at the end, so one in the middle is the value's own text."""
    rendering = '[{"id":"a<cut 9 chars>b"}]'
    assert trailwidth.read_line(trail(rendering)) == trailwidth.Reading(
        len(rendering), 1, cut=False
    )


def test_read_line_counts_no_candidates_on_a_rendering_that_is_not_a_list() -> None:
    assert trailwidth.read_line(trail('{"id":"a"}')) == trailwidth.Reading(10, None, cut=False)


def test_read_line_counts_no_candidates_on_a_rendering_that_will_not_parse() -> None:
    assert trailwidth.read_line(trail("[oops")) == trailwidth.Reading(5, None, cut=False)


def test_readings_keeps_every_trail_line_in_the_captures_own_order() -> None:
    text = "\n".join([trail('[{"id":"a"}]'), "unrelated line", trail("[]")])
    assert [reading.width for reading in trailwidth.readings(text)] == [12, 2]


def test_load_reads_a_capture_into_a_block(tmp_path: Path) -> None:
    block = trailwidth.load(capture(tmp_path / "b.log", trail("[]"), trail('[{"id":"a"}]')))
    assert block.path.name == "b.log"
    assert block.widths == (2, 12)
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


def test_by_entries_groups_widths_by_the_candidates_the_line_named(tmp_path: Path) -> None:
    block = trailwidth.load(
        capture(
            tmp_path / "g.log",
            trail('[{"id":"a"}]'),
            trail('[{"id":"ab"}]'),
            trail('[{"id":"a"},{"id":"b"}]'),
        )
    )
    assert trailwidth.by_entries([block]) == {1: [12, 13], 2: [23]}


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
    assert "over all 3 lines: 2 to 14 chars" in text
    assert "cut by the bound: 0" in text


def test_report_reads_a_cohort_per_candidate(tmp_path: Path) -> None:
    block = trailwidth.load(capture(tmp_path / "p.log", trail('[{"id":"a"},{"id":"b"}]')))
    assert "2 dropped (n=   1): 23 to 23 chars" in trailwidth.report([block], resamples=50, seed=7)
    assert "11.50 to 11.50 per candidate" in trailwidth.report([block], resamples=50, seed=7)


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
    assert "over all 1 lines: 12 to 12 chars" in capsys.readouterr().out


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
