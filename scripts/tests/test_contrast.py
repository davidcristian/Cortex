import json
from pathlib import Path

import pytest

import contrast


def turn(question: str, ttft: float, wall: float) -> dict[str, object]:
    return {"question": question, "ttft": ttft, "wall": wall}


def sample(arm: str, turns: list[dict[str, object]]) -> dict[str, object]:
    return {"arm": arm, "turns": turns}


def write(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def block(path: Path, arm: str, pairs: list[tuple[str, float]]) -> contrast.Block:
    turns = [turn(question, value, value + 0.5) for question, value in pairs]
    return contrast.load(write(path, sample(arm, turns)))


def test_load_reads_arm_and_every_turn(tmp_path: Path) -> None:
    loaded = block(tmp_path / "a.json", "raw", [("q1", 1.0), ("q2", 2.0)])
    assert loaded.arm == "raw"
    assert loaded.path.name == "a.json"
    assert loaded.turns == (
        ("q1", {"ttft": 1.0, "wall": 1.5}),
        ("q2", {"ttft": 2.0, "wall": 2.5}),
    )


def test_load_refuses_a_file_it_cannot_read(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="unreadable sample"):
        contrast.load(tmp_path / "missing.json")


def test_load_refuses_text_that_is_not_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(contrast.ContrastError, match="unreadable sample"):
        contrast.load(path)


def test_load_refuses_a_sample_that_is_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="must be a JSON object"):
        contrast.load(write(tmp_path / "list.json", [1, 2, 3]))


def test_load_refuses_a_sample_naming_no_arm(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="names no arm"):
        contrast.load(write(tmp_path / "n.json", {"turns": [turn("q", 1.0, 1.5)]}))


def test_load_refuses_a_sample_carrying_no_turns_list(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="carries no turns list"):
        contrast.load(write(tmp_path / "n.json", {"arm": "raw", "turns": "several"}))


def test_load_refuses_a_turn_that_is_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="not a JSON object"):
        contrast.load(write(tmp_path / "n.json", sample("raw", ["q1"])))  # type: ignore[list-item]


def test_load_refuses_a_turn_naming_no_question(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="names no question"):
        contrast.load(write(tmp_path / "n.json", sample("raw", [{"ttft": 1.0, "wall": 1.5}])))


def test_load_refuses_a_turn_missing_a_metric(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="missing one of"):
        contrast.load(write(tmp_path / "n.json", sample("raw", [{"question": "q", "ttft": 1.0}])))


def test_load_refuses_a_sample_with_no_turns_at_all(tmp_path: Path) -> None:
    with pytest.raises(contrast.ContrastError, match="holds no turns"):
        contrast.load(write(tmp_path / "n.json", sample("raw", [])))


def test_by_question_averages_the_repetitions_of_each_question(tmp_path: Path) -> None:
    loaded = block(tmp_path / "a.json", "raw", [("q1", 1.0), ("q1", 3.0), ("q2", 4.0)])
    assert contrast.by_question(loaded, "ttft") == {"q1": 2.0, "q2": 4.0}


def test_summarize_reports_the_unblocked_shape(tmp_path: Path) -> None:
    loaded = block(tmp_path / "a.json", "raw", [("q1", 1.0), ("q2", 3.0), ("q3", 5.0)])
    assert contrast.summarize(loaded, "ttft") == contrast.Summary(3, 3.0, 3.0, 2.0)


def test_summarize_calls_a_single_turns_deviation_zero(tmp_path: Path) -> None:
    loaded = block(tmp_path / "a.json", "raw", [("q1", 1.0)])
    assert contrast.summarize(loaded, "ttft") == contrast.Summary(1, 1.0, 1.0, 0.0)


def test_differences_pairs_question_by_question(tmp_path: Path) -> None:
    baseline = block(tmp_path / "a.json", "raw", [("q1", 1.0), ("q2", 2.0)])
    arm = block(tmp_path / "b.json", "judge", [("q2", 2.5), ("q1", 1.5)])
    assert contrast.differences(baseline, arm, "ttft") == [0.5, 0.5]


def test_differences_refuses_blocks_that_asked_different_questions(tmp_path: Path) -> None:
    baseline = block(tmp_path / "a.json", "raw", [("q1", 1.0)])
    arm = block(tmp_path / "b.json", "judge", [("q9", 1.0)])
    with pytest.raises(contrast.ContrastError, match="cannot be paired"):
        contrast.differences(baseline, arm, "ttft")


def test_percentile_of_a_single_value_is_that_value() -> None:
    assert contrast.percentile([4.0], 0.5) == 4.0


def test_percentile_lands_exactly_on_a_sample_when_the_position_is_whole() -> None:
    assert contrast.percentile([1.0, 2.0, 3.0], 0.5) == 2.0


def test_percentile_interpolates_between_the_two_neighbours() -> None:
    assert contrast.percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5


def test_bootstrap_brackets_the_point_estimate() -> None:
    interval = contrast.bootstrap([1.0, 2.0, 3.0, 4.0], resamples=500, seed=7)
    assert interval.point == 2.5
    assert interval.low < interval.point < interval.high


def test_bootstrap_is_a_function_of_its_seed() -> None:
    values = [0.1, 0.6, 0.2, 0.9, 0.4]
    assert contrast.bootstrap(values, resamples=200, seed=1) == contrast.bootstrap(
        values, resamples=200, seed=1
    )
    assert contrast.bootstrap(values, resamples=200, seed=1) != contrast.bootstrap(
        values, resamples=200, seed=2
    )


def test_bootstrap_refuses_a_contrast_over_nothing() -> None:
    with pytest.raises(contrast.ContrastError, match="no questions"):
        contrast.bootstrap([], resamples=10, seed=1)


def test_report_stars_an_interval_that_clears_zero(tmp_path: Path) -> None:
    baseline = block(tmp_path / "a.json", "raw", [("q1", 1.0), ("q2", 2.0), ("q3", 3.0)])
    arm = block(tmp_path / "b.json", "judge", [("q1", 6.0), ("q2", 7.0), ("q3", 8.0)])
    text = contrast.report([baseline, arm], resamples=200, seed=3)
    assert "judge (b.json) ttft: +5.000s" in text
    assert "* an interval that does not span zero." in text
    assert "+5.000s (95% CI +5.000 to +5.000) *" in text


def test_report_leaves_a_null_contrast_unstarred(tmp_path: Path) -> None:
    baseline = block(tmp_path / "a.json", "raw", [("q1", 1.0), ("q2", 2.0), ("q3", 9.0)])
    arm = block(tmp_path / "c.json", "raw", [("q1", 2.0), ("q2", 1.0), ("q3", 9.0)])
    text = contrast.report([baseline, arm], resamples=400, seed=3)
    lines = [line for line in text.splitlines() if line.startswith("  raw (c.json)")]
    assert len(lines) == len(contrast.METRICS)
    assert [line for line in lines if line.endswith("*")] == []


def test_report_lays_out_every_question_the_blocking_used(tmp_path: Path) -> None:
    baseline = block(tmp_path / "a.json", "raw", [("cheap", 1.0), ("dear", 4.0)])
    arm = block(tmp_path / "b.json", "judge", [("cheap", 1.1), ("dear", 7.0)])
    text = contrast.report([baseline, arm], resamples=50, seed=3)
    assert "per question, ttft against raw (a.json):" in text
    assert "  1.00s  +0.10s  cheap" in text
    assert "  4.00s  +3.00s  dear" in text


def test_report_names_every_block_and_the_seed(tmp_path: Path) -> None:
    baseline = block(tmp_path / "a.json", "raw", [("q1", 1.0)])
    arm = block(tmp_path / "b.json", "judge", [("q1", 2.0)])
    text = contrast.report([baseline, arm], resamples=10, seed=42)
    assert "blocks: 2, resamples: 10, seed: 42" in text
    assert "raw (a.json, n=1)" in text
    assert "judge (b.json, n=1)" in text


def test_main_prints_the_report_and_succeeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = write(tmp_path / "a.json", sample("raw", [turn("q1", 1.0, 1.5)]))
    second = write(tmp_path / "b.json", sample("judge", [turn("q1", 2.0, 2.5)]))
    code = main_with([str(first), str(second), "--resamples", "20", "--seed", "5"])
    assert code == 0
    assert "judge (b.json) ttft: +1.000s" in capsys.readouterr().out


def main_with(argv: list[str]) -> int:
    return contrast.main(argv)


def test_main_refuses_a_single_sample(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    only = write(tmp_path / "a.json", sample("raw", [turn("q1", 1.0, 1.5)]))
    assert main_with([str(only)]) == 2
    assert "needs a baseline block" in capsys.readouterr().err


def test_main_refuses_a_bootstrap_of_no_resamples(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = write(tmp_path / "a.json", sample("raw", [turn("q1", 1.0, 1.5)]))
    second = write(tmp_path / "b.json", sample("judge", [turn("q1", 2.0, 2.5)]))
    assert main_with([str(first), str(second), "--resamples", "0"]) == 2
    assert "at least one resample" in capsys.readouterr().err


def test_main_reports_an_unreadable_sample_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = write(tmp_path / "a.json", sample("raw", [turn("q1", 1.0, 1.5)]))
    assert main_with([str(first), str(tmp_path / "gone.json")]) == 2
    assert "contrast: " in capsys.readouterr().err
