import json
from pathlib import Path

import pytest

import envelopefloor
from envelopejudges import Reading
from envelopesamples import Turn, load

# One run of a sample, as JSON rather than as a parsed turn: these fixtures are the driver's own
# output and the reader's rates are computed over what arrives in it.
type Run = dict[str, object]

# The subtask the shipped harness asks, and the same subtask once the runner has appended the
# constrained path's own sentence. Two shapes of one ask, which is what the shape grouping is over.
ASK = "Summarize the report below, keeping every detail."
SENT = f"{ASK} Your entire response must be the answer itself."
EXTRACT = "Extract every number from the report below."
LOOKUP = "What reporting period does the report below cover?"
LIMERICK = "Write a limerick about the report below."

# One report body, an answer that recalls every number in it, and a narration that recalls none.
BODY = "Site report, north warehouse, week 34. Inbound pallets 1,842, up from 1,610."
FORTNIGHT = "Network operations report, fortnight 18. Core availability 99.97%."
ANSWER = "week 34: 1,842 pallets inbound, against 1,610 the week before."
NARRATION = "The user wants a summary of the provided site report."


def turn(
    *,
    instruction: str = ASK,
    context: str = BODY,
    ok: bool = True,
    output: str = ANSWER,
) -> Run:
    """Return one run as the driver writes it, defaulting to a run that stood and delivered."""
    return {
        "question": "warehouse",
        "instruction": instruction,
        "context": context,
        "ok": ok,
        "output": output,
    }


def runs(
    count: int,
    *,
    instruction: str = ASK,
    context: str = BODY,
    ok: bool = True,
    output: str = ANSWER,
) -> list[Run]:
    """``count`` runs of one kind, as the driver would have written them."""
    made = turn(instruction=instruction, context=context, ok=ok, output=output)
    return [dict(made) for _ in range(count)]


def sample(path: Path, arm: str, rows: list[Run], *, control: bool) -> Path:
    """Write one arm's sample file the way the driver writes it."""
    path.write_text(json.dumps({"arm": arm, "control": control, "turns": rows}), encoding="utf-8")
    return path


def cell(count: int, of: int) -> tuple[Turn, ...]:
    """``of`` runs of which ``count`` stood and delivered, the rest handing the instruction back."""
    good = [Turn(ASK, BODY, ok=True, output=ANSWER) for _ in range(count)]
    bad = [Turn(ASK, BODY, ok=True, output=ASK) for _ in range(of - count)]
    return tuple(good + bad)


def test_the_interval_reproduces_the_published_rates() -> None:
    """Ten of the rates the ADR-0028 addenda published by hand, recomputed here. The arithmetic
    moved into this file to be covered, and a different arithmetic would rewrite every number the
    record already carries."""
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
    for (count, of), claimed in published.items():
        low, high = envelopefloor.wilson(count, of)
        assert (round(low, 2), round(high, 2)) == claimed, f"{count} of {of}"


def test_a_cell_is_refused_only_when_its_whole_interval_is_under_the_floor() -> None:
    """The test is one-sided deliberately: a failure has to be proven, so a point estimate under
    the floor is not enough, and 26 of 32 passes where 25 of 32 does not."""
    assert not envelopefloor.rate(cell(26, 32)).refused
    assert envelopefloor.rate(cell(25, 32)).refused


def test_a_four_run_probe_fails_only_once_half_of_it_has_failed() -> None:
    """The default settings draw four runs an arm, where one loss is a quarter of the sample and
    evidence of nothing, while half of them failing is a claim the interval supports."""
    assert not envelopefloor.rate(cell(3, 4)).refused
    assert envelopefloor.rate(cell(2, 4)).refused


def test_a_rate_counts_its_lapses_by_kind() -> None:
    found = envelopefloor.rate(
        (
            Turn(ASK, BODY, ok=True, output=ANSWER),
            Turn(ASK, BODY, ok=False, output="cut"),
            Turn(ASK, BODY, ok=True, output=ASK),
            Turn(ASK, BODY, ok=True, output=""),
        )
    )
    assert found.stood == 1
    assert found.runs == 4
    assert found.lapses == (("echo", 1), ("empty", 1), ("refused", 1))
    assert "stood on 1 of 4" in found.rendered()
    assert "lapses: echo 1, empty 1, refused 1" in found.rendered()


def test_a_rate_with_nothing_to_report_renders_no_lapse_clause() -> None:
    assert envelopefloor.rate(cell(4, 4)).rendered().endswith(")")


def test_a_narration_stands_and_does_not_deliver() -> None:
    """The two rates on one cell, and the gap between them is this reader's whole subject: every
    one of these replies is well formed, accepted and not an echo, and none of them answers."""
    narrating = tuple(Turn(ASK, BODY, ok=True, output=NARRATION) for _ in range(8))
    found = envelopefloor.rate(narrating)
    assert found.stood == 8
    assert found.delivery is not None
    assert (found.delivery.delivered, found.delivery.judged) == (0, 8)
    assert found.rendered() == "stood on 8 of 8 (0.68 to 1.00), delivered 0 of 8 (0.00 to 0.32)"


def test_a_shape_no_judge_is_declared_for_publishes_stood_alone_and_says_so() -> None:
    """The harness lets the subtask be anything, so a run with a hand typed instruction is a run
    this reader can count and cannot judge, and the line says which."""
    typed = tuple(Turn(LIMERICK, BODY, ok=True, output="there once was a warehouse") for _ in "ab")
    found = envelopefloor.rate(typed)
    assert found.delivery is None
    assert found.rendered().endswith("no judge is declared for this shape")


def test_a_cell_is_judged_over_the_runs_a_judge_could_read() -> None:
    """One body of a cell stating no number leaves that run unjudged rather than counted either
    way, so the delivered denominator is the runs judged and is printed as such."""
    mixed = (
        Turn(ASK, BODY, ok=True, output=ANSWER),
        Turn(ASK, "a report stating no number at all", ok=True, output=ANSWER),
    )
    found = envelopefloor.rate(mixed)
    assert found.delivery is not None
    assert (found.delivery.delivered, found.delivery.judged, found.runs) == (1, 1, 2)


def test_shapes_group_by_the_instruction_the_arm_really_sent() -> None:
    """A subtask shape is its instruction, and the sentence the constrained path appends makes
    the same subtask a different shape, which is why the control arm is grouped on its own."""
    grouped = envelopefloor.shapes(
        (
            Turn(ASK, BODY, ok=True, output="a"),
            Turn(EXTRACT, BODY, ok=True, output="b"),
            Turn(ASK, BODY, ok=True, output="c"),
        )
    )
    assert list(grouped) == [ASK, EXTRACT]
    assert len(grouped[ASK]) == 2


def test_publish_reports_the_control_arm_then_the_comparison(tmp_path: Path) -> None:
    arms = [
        load(sample(tmp_path / "raw.json", "raw", runs(32), control=True)),
        load(
            sample(
                tmp_path / "con.json",
                "constrained",
                runs(30, instruction=SENT) + runs(2, instruction=SENT, output=SENT),
                control=False,
            )
        ),
    ]
    report, code = envelopefloor.publish(arms)
    assert code == 0
    assert "stood on 32 of 32 (0.89 to 1.00), delivered 32 of 32 (0.89 to 1.00)" in report
    assert "delivered read under: comma charitable, refusal strict, naming strict" in report
    assert "the comparison, per arm over every shape:" in report
    assert "constrained stood on 30 of 32 (0.80 to 0.98), delivered 30 of 32" in " ".join(
        report.split()
    )


def test_publish_refuses_a_comparison_read_against_a_collapsed_control(tmp_path: Path) -> None:
    """A control arm that failed the subtask would leave a tidy table pricing the pick, and that
    table is what must not be printed."""
    collapsed = runs(20) + runs(12, output=ASK)
    arms = [
        load(sample(tmp_path / "raw.json", "raw", collapsed, control=True)),
        load(sample(tmp_path / "con.json", "constrained", runs(32), control=False)),
    ]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "refused: 1 of 1 control cell(s) stood on fewer than 90% of their own runs" in report
    assert "the comparison, per arm" not in report


def test_publish_refuses_a_control_arm_that_stood_and_did_not_answer(tmp_path: Path) -> None:
    """The failure the machine-read rate cannot see on its own. Every one of these runs is
    accepted, non empty and not the ask handed back, and not one of them answers the subtask."""
    narrating = runs(30, output=NARRATION) + runs(2)
    arms = [load(sample(tmp_path / "raw.json", "raw", narrating, control=True))]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "stood on 32 of 32" in report
    assert "refused: 1 of 1 control cell(s) delivered on fewer than 90% of the runs" in report
    assert "the comparison, per arm" not in report


def test_a_floor_is_held_under_the_tabled_reading_whatever_columns_were_asked_for(
    tmp_path: Path,
) -> None:
    """A verdict that moved with a flag would be the rejected floor knob under another name. The
    charitable naming column reads every one of these lookup replies as an answer; the refusal is
    taken under the column the record's own rows are in and does not move."""
    garbled = runs(32, instruction=LOOKUP, context=FORTNIGHT, output="Fortnite 18")
    arms = [load(sample(tmp_path / "raw.json", "raw", garbled, control=True))]
    report, code = envelopefloor.publish(arms, Reading(naming="charitable"))
    assert code == 1
    assert "delivered 32 of 32" in report
    assert "refused: 1 of 1 control cell(s) delivered on fewer than 90%" in report


def test_publish_refuses_when_one_shape_of_several_collapsed(tmp_path: Path) -> None:
    """Cells are judged per shape rather than pooled: a pick that answers a summarization and
    cannot do an extraction has one cell at the ceiling and one on the floor, and their average
    describes neither."""
    both = runs(32) + runs(32, instruction=EXTRACT, output=EXTRACT)
    arms = [load(sample(tmp_path / "raw.json", "raw", both, control=True))]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "refused: 1 of 2 control cell(s) stood" in report
    assert "refused: 1 of 2 control cell(s) delivered" in report


def test_publish_refuses_a_run_that_drew_no_control_arm(tmp_path: Path) -> None:
    """A probe may run any subset of the arms, so the control arm can be absent entirely, and a
    comparison with no control in it reads nothing at all."""
    arms = [load(sample(tmp_path / "con.json", "constrained", runs(8), control=False))]
    report, code = envelopefloor.publish(arms)
    assert code == 1
    assert "none of these samples is the control arm" in report
    assert "the comparison, per arm" not in report


def test_main_publishes_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = sample(tmp_path / "raw.json", "raw", runs(32), control=True)
    assert envelopefloor.main([str(path)]) == 0
    assert "the comparison, per arm over every shape:" in capsys.readouterr().out


def test_main_reads_the_columns_it_was_asked_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same replies under the separator reading of a comma, which is the arbitration the
    lineup addendum introduced and published as a column. The column moves and the verdict does
    not, since the floor is held under the reading the record's own rows are in."""
    listed = runs(32, output="1,842, 1,610, 34")
    path = sample(tmp_path / "raw.json", "raw", listed, control=True)
    assert envelopefloor.main([str(path)]) == 0
    assert "delivered 32 of 32" in capsys.readouterr().out
    assert envelopefloor.main(["--comma", "separator", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "delivered 0 of 32" in printed
    assert "delivered read under: comma separator" in printed


def test_main_returns_one_when_it_refuses_to_publish(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    collapsed = runs(20) + runs(12, output=ASK)
    path = sample(tmp_path / "raw.json", "raw", collapsed, control=True)
    assert envelopefloor.main([str(path)]) == 1
    assert "refused:" in capsys.readouterr().out


def test_main_returns_two_on_a_sample_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert envelopefloor.main([str(tmp_path / "absent.json")]) == 2
    assert "envelopefloor:" in capsys.readouterr().err
