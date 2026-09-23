import json
from pathlib import Path

import pytest

import envelopesamples

type Run = dict[str, object]

ASK = "Summarize the report below, keeping every detail."
BODY = "Site report, north warehouse, week 34. Inbound pallets 1,842."


def turn(*, instruction: str = ASK, ok: bool = True, output: str = "a summary, in full") -> Run:
    """Return one run as the driver writes it, by default one that succeeded."""
    return {
        "question": "warehouse",
        "instruction": instruction,
        "context": BODY,
        "ok": ok,
        "output": output,
    }


def sample(path: Path, variant: str, turns: list[Run], *, control: bool) -> Path:
    """Write one variant's sample file the way the driver writes it."""
    path.write_text(
        json.dumps({"arm": variant, "control": control, "turns": turns}), encoding="utf-8"
    )
    return path


def test_a_refused_run_is_a_lapse_whatever_its_text_held() -> None:
    assert envelopesamples.Turn(ASK, BODY, ok=False, output="a summary, in full").lapse == "refused"


def test_an_accepted_but_empty_reply_is_a_lapse() -> None:
    assert envelopesamples.Turn(ASK, BODY, ok=True, output="   \n ").lapse == "empty"


def test_the_instruction_handed_back_is_a_lapse_through_punctuation_and_case() -> None:
    assert envelopesamples.Turn(ASK, BODY, ok=True, output=ASK).lapse == "echo"
    assert envelopesamples.Turn(ASK, BODY, ok=True, output=f"  {ASK.upper()}  ").lapse == "echo"


def test_a_reply_that_quotes_the_instruction_on_its_way_to_answering_is_not_an_echo() -> None:
    quoting = envelopesamples.Turn(ASK, BODY, ok=True, output=f"{ASK} Inbound pallets 1,842.")
    assert quoting.lapse is None


def test_an_answer_this_reader_cannot_judge_structurally_is_not_a_lapse() -> None:
    narrating = envelopesamples.Turn(ASK, BODY, ok=True, output="The user wants a summary.")
    assert narrating.lapse is None


def test_load_reads_one_variants_sample(tmp_path: Path) -> None:
    variant = envelopesamples.load(
        sample(tmp_path / "raw.json", "raw", [turn(), turn()], control=True)
    )
    assert (variant.name, variant.control, len(variant.turns)) == ("raw", True, 2)
    assert variant.turns[0].instruction == ASK
    assert variant.turns[0].context == BODY


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


def test_load_refuses_a_sample_that_names_no_variant(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"control": True, "turns": [turn()]}), encoding="utf-8")
    with pytest.raises(envelopesamples.FloorError, match="arm is missing"):
        envelopesamples.load(path)


def test_load_refuses_a_sample_that_does_not_say_whether_it_is_the_control(tmp_path: Path) -> None:
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
    old: Run = {"question": "warehouse", "context": BODY, "ok": True, "output": "a summary"}
    with pytest.raises(envelopesamples.FloorError, match="instruction is missing"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [old], control=True))


def test_load_refuses_a_turn_written_before_the_driver_recorded_the_body(tmp_path: Path) -> None:
    old: Run = {"question": "warehouse", "instruction": ASK, "ok": True, "output": "a summary"}
    with pytest.raises(envelopesamples.FloorError, match="context is missing"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [old], control=True))


def test_a_turn_that_does_not_say_whether_it_was_accepted_is_refused(tmp_path: Path) -> None:
    broken: Run = {"instruction": ASK, "context": BODY, "output": "a summary, in full"}
    with pytest.raises(envelopesamples.FloorError, match="ok is missing"):
        envelopesamples.load(sample(tmp_path / "raw.json", "raw", [broken], control=True))


def test_the_report_body_handed_back_is_a_lapse() -> None:
    assert envelopesamples.Turn(ASK, BODY, ok=True, output=BODY.upper()).lapse == "copy"


def test_a_copy_is_not_read_on_a_shape_no_judge_is_declared_for() -> None:
    proofread = "Correct the spelling in the report below."
    assert envelopesamples.Turn(proofread, BODY, ok=True, output=BODY).lapse is None


def paired(**fields: object) -> Run:
    """Return one run as a seeded driver writes it, with ``fields`` replacing its defaults."""
    return {**turn(), "draw": 1, "seed": 7, "tokens": 90, **fields}


def test_cells_reads_where_each_run_sits_and_what_it_drew(tmp_path: Path) -> None:
    path = sample(tmp_path / "a.json", "raw", [paired(), paired(draw=2, seed=None)], control=True)
    variant, found = envelopesamples.cells(path)
    assert variant == "raw"
    assert found[0] == envelopesamples.Cell(
        "warehouse", 1, 7, (ASK, BODY), "a summary, in full", 90
    )
    assert (found[1].draw, found[1].seed) == (2, None)


def test_cells_refuses_a_run_written_before_the_driver_recorded_its_seed(tmp_path: Path) -> None:
    old = turn() | {"draw": 1, "tokens": 90}
    with pytest.raises(envelopesamples.FloorError, match="seed is missing"):
        envelopesamples.cells(sample(tmp_path / "a.json", "raw", [old], control=True))


def test_cells_refuses_a_count_that_is_not_an_integer(tmp_path: Path) -> None:
    for broken in (paired(seed="7"), paired(draw=True)):
        path = sample(tmp_path / "a.json", "raw", [broken], control=True)
        with pytest.raises(envelopesamples.FloorError, match="is not an integer or null"):
            envelopesamples.cells(path)
