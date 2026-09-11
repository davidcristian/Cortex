import json
from pathlib import Path

import pytest

import envelopepairs

type Run = dict[str, object]

ASK = "Summarize the report below, keeping every detail."
BODY = "Site report, north warehouse, week 34. Inbound pallets 1,842."


def run(question: str = "warehouse", draw: int = 1, **fields: object) -> Run:
    """One run as the driver writes it, seeded by its draw unless ``fields`` says otherwise."""
    base: Run = {
        "question": question,
        "draw": draw,
        "seed": draw,
        "instruction": ASK,
        "context": BODY,
        "ok": True,
        "output": f"{question} {draw}",
        "tokens": 100,
    }
    return base | fields


def write(path: Path, turns: list[Run], arm: str = "constrained") -> Path:
    path.write_text(json.dumps({"arm": arm, "control": False, "turns": turns}), encoding="utf-8")
    return path


def two() -> list[Run]:
    """The two cells every sample here holds unless a test says otherwise."""
    return [run("warehouse", 1), run("clinic", 1)]


def test_two_identical_runs_are_identical_on_every_cell(tmp_path: Path) -> None:
    left = write(tmp_path / "a.json", two())
    right = write(tmp_path / "b.json", two())
    assert envelopepairs.main([str(left), str(right)]) == 0


def test_a_cell_differing_in_output_or_in_tokens_is_named(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    left = write(tmp_path / "a.json", two())
    right = write(tmp_path / "b.json", [run("warehouse", 1, output="else"), run("clinic", 1)])
    tokens = write(tmp_path / "c.json", [run("warehouse", 1), run("clinic", 1, tokens=101)])
    assert envelopepairs.main([str(left), str(right), str(tokens)]) == 0
    report = capsys.readouterr().out.splitlines()
    assert (
        report[0]
        == "3 samples of arm constrained, 2 cells each, matched on question, draw and seed:"
    )
    counted = "identical in output and tokens; differ at"
    assert report[1] == f"  {left} against {right}: 1 of 2 {counted} warehouse draw 1 seed 1"
    assert report[2] == f"  {left} against {tokens}: 1 of 2 {counted} clinic draw 1 seed 1"
    both = "warehouse draw 1 seed 1, clinic draw 1 seed 1"
    assert report[3] == f"  {right} against {tokens}: 0 of 2 {counted} {both}"


def test_cells_are_matched_on_their_place_rather_than_their_order(tmp_path: Path) -> None:
    left = write(tmp_path / "a.json", two())
    right = write(tmp_path / "b.json", list(reversed(two())))
    report, code = envelopepairs.publish(
        [envelopepairs.Sample(path, *envelopepairs.cells(path)) for path in (left, right)]
    )
    assert (code, report.splitlines()[1].split(": ")[1]) == (
        0,
        "2 of 2 identical in output and tokens",
    )


@pytest.mark.parametrize(
    ("second", "arm", "reason"),
    [
        ([run("warehouse", 1, seed=None), run("clinic", 1)], "constrained", "carries a null seed"),
        ([run("warehouse", 1), run("warehouse", 1)], "constrained", "holds one cell twice"),
        (two(), "raw", "is arm raw and"),
        ([run("warehouse", 1), run("fleet", 1)], "constrained", "does not hold the cells"),
        ([run("warehouse", 1, seed=5), run("clinic", 1)], "constrained", "does not hold the cells"),
        (
            [run("warehouse", 1), run("clinic", 1, context="another body")],
            "constrained",
            "another instruction or body at clinic draw 1 seed 1",
        ),
        (
            [run("warehouse", 1, instruction="Extract every number."), run("clinic", 1)],
            "constrained",
            "another instruction or body at warehouse draw 1 seed 1",
        ),
    ],
)
def test_samples_that_do_not_pair_are_refused(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, second: list[Run], arm: str, reason: str
) -> None:
    """A seed claims one completion per prompt, so nothing else is counted as a pair."""
    left = write(tmp_path / "a.json", two())
    right = write(tmp_path / "b.json", second, arm)
    assert envelopepairs.main([str(left), str(right)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("refused: ")
    assert reason in out


def test_one_sample_pairs_with_nothing(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert envelopepairs.main([str(write(tmp_path / "a.json", two()))]) == 1
    assert capsys.readouterr().out == "refused: a pairing needs two samples or more\n"


def test_an_unreadable_sample_exits_two(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    left = write(tmp_path / "a.json", two())
    assert envelopepairs.main([str(left), str(tmp_path / "absent.json")]) == 2
    assert capsys.readouterr().err.startswith("envelopepairs: ")
