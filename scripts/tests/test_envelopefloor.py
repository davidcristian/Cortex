import json
from pathlib import Path

import pytest

import envelopefloor

# One run of a sample, as JSON rather than as a parsed turn: these fixtures are the driver's own
# output and the reader's refusals are about the shapes that arrive in it.
type Run = dict[str, object]

# The subtask the shipped harness asks, and the same subtask once the runner has appended the
# constrained path's own sentence. Two shapes of one ask, which is what the shape grouping is over.
ASK = "Summarize the report below, keeping every detail."
SENT = f"{ASK} Your entire response must be the answer itself."


def turn(*, instruction: str = ASK, ok: bool = True, output: str = "a summary, in full") -> Run:
    """One run as the driver writes it, defaulting to a run that stood."""
    return {"question": "warehouse", "instruction": instruction, "ok": ok, "output": output}


def sample(path: Path, arm: str, turns: list[Run], *, control: bool) -> Path:
    """One arm's sample file, written the way the driver writes it."""
    path.write_text(json.dumps({"arm": arm, "control": control, "turns": turns}), encoding="utf-8")
    return path


def stood(count: int, *, instruction: str = ASK) -> list[Run]:
    return [turn(instruction=instruction) for _ in range(count)]


def test_a_refused_run_is_a_lapse_whatever_its_text_held() -> None:
    """The runner already settled it, and a cut reply carries the text it had got to."""
    assert envelopefloor.Turn(ASK, ok=False, output="a summary, in full").lapse == "refused"


def test_an_accepted_but_empty_reply_is_a_lapse() -> None:
    assert envelopefloor.Turn(ASK, ok=True, output="   \n ").lapse == "empty"


def test_the_instruction_handed_back_is_a_lapse_through_punctuation_and_case() -> None:
    """The quiet failure this tier really produces, and it is read over letters and digits so a
    reply that differs from the ask by a full stop or a capital is still the ask."""
    assert envelopefloor.Turn(ASK, ok=True, output=ASK).lapse == "echo"
    assert envelopefloor.Turn(ASK, ok=True, output=f"  {ASK.upper()}  ").lapse == "echo"


def test_a_reply_that_quotes_the_instruction_on_its_way_to_answering_is_not_an_echo() -> None:
    """Equality and not containment: the echo rule may not call a real answer a failure."""
    assert envelopefloor.Turn(ASK, ok=True, output=f"{ASK} Inbound pallets 1,842.").lapse is None


def test_an_answer_this_reader_cannot_judge_is_not_a_lapse() -> None:
    """The half that stays a reading. A narration is a well formed reply about the task, and
    nothing structural separates it from an answer, which is why `stood` bounds `delivered`
    from above rather than measuring it."""
    assert envelopefloor.Turn(ASK, ok=True, output="The user wants a summary.").lapse is None


def test_the_interval_reproduces_the_published_rates() -> None:
    """Ten of the rates the ADR-0028 addenda published by hand, recomputed here. The arithmetic
    moved into this file to be covered; a different arithmetic would have quietly rewritten every
    number the record already carries."""
    published = {
        (32, 32): (0.89, 1.00),
        (31, 32): (0.84, 0.99),
        (30, 32): (0.80, 0.98),
        (19, 32): (0.42, 0.74),
        (12, 32): (0.23, 0.55),
        (9, 32): (0.16, 0.45),
        (96, 96): (0.96, 1.00),
        (93, 96): (0.91, 0.99),
        (72, 96): (0.65, 0.83),
        (66, 96): (0.59, 0.77),
    }
    for (count, runs), claimed in published.items():
        low, high = envelopefloor.wilson(count, runs)
        assert (round(low, 2), round(high, 2)) == claimed, f"{count} of {runs}"


def test_a_cell_is_refused_only_when_its_whole_interval_is_under_the_floor() -> None:
    """One-sided on purpose: a red has to be a proof, so the point estimate falling under the
    floor is not enough and 26 of 32 passes where 25 of 32 does not."""
    assert not envelopefloor.rate(_cell(26, 32)).refused
    assert envelopefloor.rate(_cell(25, 32)).refused


def test_a_four_run_probe_reddens_only_once_half_of_it_has_failed() -> None:
    """The default knobs draw four runs an arm, where one loss is a quarter of the sample and
    evidence of nothing; half of them failing is a different claim, and the interval says so."""
    assert not envelopefloor.rate(_cell(3, 4)).refused
    assert envelopefloor.rate(_cell(2, 4)).refused


def _cell(count: int, runs: int) -> tuple[envelopefloor.Turn, ...]:
    """``runs`` runs of which ``count`` stood, the rest handing the instruction back."""
    good = [envelopefloor.Turn(ASK, ok=True, output="a summary, in full") for _ in range(count)]
    bad = [envelopefloor.Turn(ASK, ok=True, output=ASK) for _ in range(runs - count)]
    return tuple(good + bad)


def test_a_rate_counts_its_lapses_by_kind() -> None:
    found = envelopefloor.rate(
        (
            envelopefloor.Turn(ASK, ok=True, output="a summary, in full"),
            envelopefloor.Turn(ASK, ok=False, output="cut"),
            envelopefloor.Turn(ASK, ok=True, output=ASK),
            envelopefloor.Turn(ASK, ok=True, output=""),
        )
    )
    assert found.stood == 1
    assert found.runs == 4
    assert found.lapses == (("echo", 1), ("empty", 1), ("refused", 1))
    assert "stood on 1 of 4" in found.rendered()
    assert "lapses: echo 1, empty 1, refused 1" in found.rendered()


def test_a_rate_with_nothing_to_report_renders_no_lapse_clause() -> None:
    assert envelopefloor.rate(_cell(4, 4)).rendered().endswith(")")


def test_shapes_group_by_the_instruction_the_arm_really_sent() -> None:
    """A subtask shape is its instruction, and the sentence the constrained path appends makes
    the same subtask a different shape, which is why the control arm is grouped on its own."""
    turns = (
        envelopefloor.Turn(ASK, ok=True, output="a"),
        envelopefloor.Turn("Extract every number from the report below.", ok=True, output="b"),
        envelopefloor.Turn(ASK, ok=True, output="c"),
    )
    grouped = envelopefloor.shapes(turns)
    assert list(grouped) == [ASK, "Extract every number from the report below."]
    assert len(grouped[ASK]) == 2


def test_load_reads_one_arms_sample(tmp_path: Path) -> None:
    arm = envelopefloor.load(sample(tmp_path / "raw.json", "raw", stood(2), control=True))
    assert (arm.name, arm.control, len(arm.turns)) == ("raw", True, 2)
    assert arm.turns[0].instruction == ASK


def test_load_refuses_a_file_it_cannot_read(tmp_path: Path) -> None:
    with pytest.raises(envelopefloor.FloorError, match="unreadable sample"):
        envelopefloor.load(tmp_path / "absent.json")


def test_load_refuses_text_that_is_not_json(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(envelopefloor.FloorError, match="unreadable sample"):
        envelopefloor.load(path)


def test_load_refuses_json_that_is_not_a_sample(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(envelopefloor.FloorError, match="a sample is a JSON object"):
        envelopefloor.load(path)


def test_load_refuses_a_sample_that_names_no_arm(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"control": True, "turns": stood(1)}), encoding="utf-8")
    with pytest.raises(envelopefloor.FloorError, match="arm is missing"):
        envelopefloor.load(path)


def test_load_refuses_a_sample_that_does_not_say_whether_it_is_the_control(tmp_path: Path) -> None:
    """The field is how the control arm is found at all, an arm's NAME being a string this reader
    would otherwise have to agree with the driver about."""
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"arm": "raw", "turns": stood(1)}), encoding="utf-8")
    with pytest.raises(envelopefloor.FloorError, match="control is missing"):
        envelopefloor.load(path)


def test_load_refuses_a_sample_carrying_no_turns_list(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"arm": "raw", "control": True, "turns": 3}), encoding="utf-8")
    with pytest.raises(envelopefloor.FloorError, match="turns is missing"):
        envelopefloor.load(path)


def test_load_refuses_a_sample_holding_no_turns(tmp_path: Path) -> None:
    with pytest.raises(envelopefloor.FloorError, match="holds no turns"):
        envelopefloor.load(sample(tmp_path / "raw.json", "raw", [], control=True))


def test_load_refuses_a_turn_that_is_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(envelopefloor.FloorError, match="a turn is not a JSON object"):
        envelopefloor.load(sample(tmp_path / "raw.json", "raw", ["a run"], control=True))  # type: ignore[list-item] -- a malformed sample is the point


def test_load_refuses_a_turn_written_before_the_driver_recorded_the_instruction(
    tmp_path: Path,
) -> None:
    """The sample format this reader needs: an older run carries no instruction, so it can be
    grouped into no shape and judged against no ask, and saying so beats guessing."""
    old: Run = {"question": "warehouse", "ok": True, "output": "a summary, in full"}
    with pytest.raises(envelopefloor.FloorError, match="instruction is missing"):
        envelopefloor.load(sample(tmp_path / "raw.json", "raw", [old], control=True))


def test_a_turn_that_does_not_say_whether_it_was_accepted_is_refused(tmp_path: Path) -> None:
    broken: Run = {"instruction": ASK, "output": "a summary, in full"}
    with pytest.raises(envelopefloor.FloorError, match="ok is missing"):
        envelopefloor.load(sample(tmp_path / "raw.json", "raw", [broken], control=True))


def test_publish_reports_the_control_arm_then_the_comparison(tmp_path: Path) -> None:
    arms = [
        envelopefloor.load(sample(tmp_path / "raw.json", "raw", stood(32), control=True)),
        envelopefloor.load(
            sample(
                tmp_path / "con.json",
                "constrained",
                [turn(instruction=SENT) for _ in range(30)]
                + [turn(instruction=SENT, output=SENT) for _ in range(2)],
                control=False,
            )
        ),
    ]
    report, code = envelopefloor.publish(arms)
    assert code == 0
    assert "stood on 32 of 32 (0.89 to 1.00)" in report
    assert "the comparison, per arm over every shape:" in report
    assert "constrained stood on 30 of 32 (0.80 to 0.98), lapses: echo 2" in " ".join(
        report.split()
    )


def test_publish_refuses_a_comparison_read_against_a_collapsed_control(tmp_path: Path) -> None:
    """The whole point: a control arm that failed the subtask leaves a tidy table pricing the
    pick, and the table is what must not be printed."""
    collapsed = stood(20) + [turn(output=ASK) for _ in range(12)]
    arms = [
        envelopefloor.load(sample(tmp_path / "raw.json", "raw", collapsed, control=True)),
        envelopefloor.load(sample(tmp_path / "con.json", "constrained", stood(32), control=False)),
    ]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "refused: 1 of 1 control cell(s) proven below 90%" in report
    assert "the comparison, per arm" not in report


def test_publish_refuses_when_one_shape_of_several_collapsed(tmp_path: Path) -> None:
    """Per shape rather than pooled: a pick that answers a summarization and cannot do an
    extraction has one cell at ceiling and one on the floor, and their average describes neither."""
    extraction = "Extract every number from the report below."
    turns = stood(32) + [turn(instruction=extraction, output=extraction) for _ in range(32)]
    arms = [envelopefloor.load(sample(tmp_path / "raw.json", "raw", turns, control=True))]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "refused: 1 of 2 control cell(s)" in report


def test_publish_refuses_a_run_that_drew_no_control_arm(tmp_path: Path) -> None:
    """A probe may run any subset of the arms, so the control arm can be absent entirely, and a
    comparison with no control in it is not a weaker reading but no reading."""
    arms = [
        envelopefloor.load(sample(tmp_path / "con.json", "constrained", stood(8), control=False))
    ]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "none of these samples is the control arm" in report
    assert "the comparison, per arm" not in report


def test_main_publishes_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = sample(tmp_path / "raw.json", "raw", stood(32), control=True)
    assert envelopefloor.main([str(path)]) == 0
    assert "the comparison, per arm over every shape:" in capsys.readouterr().out


def test_main_returns_one_when_it_refuses_to_publish(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    collapsed = stood(20) + [turn(output=ASK) for _ in range(12)]
    path = sample(tmp_path / "raw.json", "raw", collapsed, control=True)
    assert envelopefloor.main([str(path)]) == 1
    assert "refused:" in capsys.readouterr().out


def test_main_returns_two_on_a_sample_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert envelopefloor.main([str(tmp_path / "absent.json")]) == 2
    assert "envelopefloor:" in capsys.readouterr().err
