import json
from pathlib import Path

import pytest

import envelopesamples

# One run of a sample, as JSON rather than as a parsed turn: these fixtures are the driver's own
# output and the reader's refusals are about the shapes that arrive in it.
type Run = dict[str, object]

ASK = "Summarize the report below, keeping every detail."
BODY = "Site report, north warehouse, week 34. Inbound pallets 1,842."


def turn(*, instruction: str = ASK, ok: bool = True, output: str = "a summary, in full") -> Run:
    """Return one run as the driver writes it, defaulting to a run that stood."""
    return {
        "question": "warehouse",
        "instruction": instruction,
        "context": BODY,
        "ok": ok,
        "output": output,
    }


def sample(path: Path, arm: str, turns: list[Run], *, control: bool) -> Path:
    """Write one arm's sample file the way the driver writes it."""
    path.write_text(json.dumps({"arm": arm, "control": control, "turns": turns}), encoding="utf-8")
    return path


def test_a_refused_run_is_a_lapse_whatever_its_text_held() -> None:
    """A run the runner rejected is a lapse whatever its output held, since a cut reply still
    carries the text it had reached."""
    assert envelopesamples.Turn(ASK, BODY, ok=False, output="a summary, in full").lapse == "refused"


def test_an_accepted_but_empty_reply_is_a_lapse() -> None:
    assert envelopesamples.Turn(ASK, BODY, ok=True, output="   \n ").lapse == "empty"


def test_the_instruction_handed_back_is_a_lapse_through_punctuation_and_case() -> None:
    """This is the failure the tier produces most often. The comparison is over letters and digits,
    so a reply differing from the ask by a full stop or a capital is still the ask."""
    assert envelopesamples.Turn(ASK, BODY, ok=True, output=ASK).lapse == "echo"
    assert envelopesamples.Turn(ASK, BODY, ok=True, output=f"  {ASK.upper()}  ").lapse == "echo"


def test_a_reply_that_quotes_the_instruction_on_its_way_to_answering_is_not_an_echo() -> None:
    """The echo rule compares for equality rather than containment, so a real answer that quotes
    the ask on its way is not a lapse."""
    quoting = envelopesamples.Turn(ASK, BODY, ok=True, output=f"{ASK} Inbound pallets 1,842.")
    assert quoting.lapse is None


def test_an_answer_this_reader_cannot_judge_structurally_is_not_a_lapse() -> None:
    """A narration is a well formed reply about the task, and nothing structural separates it from
    an answer, which is why the shape's own judge is what counts it a non-delivery."""
    narrating = envelopesamples.Turn(ASK, BODY, ok=True, output="The user wants a summary.")
    assert narrating.lapse is None


def test_load_reads_one_arms_sample(tmp_path: Path) -> None:
    arm = envelopesamples.load(sample(tmp_path / "raw.json", "raw", [turn(), turn()], control=True))
    assert (arm.name, arm.control, len(arm.turns)) == ("raw", True, 2)
    assert arm.turns[0].instruction == ASK
    assert arm.turns[0].context == BODY


def test_load_refuses_a_file_it_cannot_read(tmp_path: Path) -> None:
    with pytest.raises(envelopesamples.FloorError, match="unreadable sample"):
        envelopesamples.load(tmp_path / "absent.json")


def test_load_refuses_text_that_is_not_json(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(envelopesamples.FloorError, match="unreadable sample"):
        envelopesamples.load(path)


def test_load_refuses_json_that_is_not_a_sample(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(envelopesamples.FloorError, match="a sample is a JSON object"):
        envelopesamples.load(path)


def test_load_refuses_a_sample_that_names_no_arm(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"control": True, "turns": [turn()]}), encoding="utf-8")
    with pytest.raises(envelopesamples.FloorError, match="arm is missing"):
        envelopesamples.load(path)


def test_load_refuses_a_sample_that_does_not_say_whether_it_is_the_control(tmp_path: Path) -> None:
    """The field is how the control arm is found, since an arm's name is a string this reader would
    otherwise have to agree with the driver about."""
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"arm": "raw", "turns": [turn()]}), encoding="utf-8")
    with pytest.raises(envelopesamples.FloorError, match="control is missing"):
        envelopesamples.load(path)


def test_load_refuses_a_sample_carrying_no_turns_list(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"arm": "raw", "control": True, "turns": 3}), encoding="utf-8")
    with pytest.raises(envelopesamples.FloorError, match="turns is missing"):
        envelopesamples.load(path)


def test_load_refuses_a_sample_holding_no_turns(tmp_path: Path) -> None:
    with pytest.raises(envelopesamples.FloorError, match="holds no turns"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [], control=True))


def test_load_refuses_a_turn_that_is_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(envelopesamples.FloorError, match="a turn is not a JSON object"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", ["a run"], control=True))  # type: ignore[list-item] -- a malformed sample is the point


def test_load_refuses_a_turn_written_before_the_driver_recorded_the_instruction(
    tmp_path: Path,
) -> None:
    """An older run carries no instruction, so it can be grouped into no shape and judged against
    no ask. The reader raises rather than supplying one."""
    old: Run = {"question": "warehouse", "context": BODY, "ok": True, "output": "a summary"}
    with pytest.raises(envelopesamples.FloorError, match="instruction is missing"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [old], control=True))


def test_load_refuses_a_turn_written_before_the_driver_recorded_the_body(tmp_path: Path) -> None:
    """A run with no body recorded can be judged by no delivered judge, both of which read a
    reply against the report it was given, so the reader raises rather than judging on the ask."""
    old: Run = {"question": "warehouse", "instruction": ASK, "ok": True, "output": "a summary"}
    with pytest.raises(envelopesamples.FloorError, match="context is missing"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [old], control=True))


def test_a_turn_that_does_not_say_whether_it_was_accepted_is_refused(tmp_path: Path) -> None:
    broken: Run = {"instruction": ASK, "context": BODY, "output": "a summary, in full"}
    with pytest.raises(envelopesamples.FloorError, match="ok is missing"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [broken], control=True))
