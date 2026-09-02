import json
from pathlib import Path

import pytest

import switchtail
from switchsamples import load
from switchtail import closes, main, marked, publish, read, tail

# The ask a run records sending; the tail is whatever a template appended after the last of it.
ASK = "What does each of them pay?"
# The four renderings this reader was written against, taken off real servers on llama.cpp
# `b10666-4e97ac86e`: Qwen3.5-0.8B Q8_0 and gemma-4-E4B QAT q4_0, the two families of the lineup on
# opposite sides of the split. The gemma pair is the hard case: its two prompts differ by a whole
# `<|think|>` system turn at the front and end byte identically, with the thought block left open.
NATIVE_OPEN = f"<|im_start|>user\n{ASK}<|im_end|>\n<|im_start|>assistant\n<think>\n"
NATIVE_SHUT = f"<|im_start|>user\n{ASK}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
GEMMA_OPEN = f"<|turn>system\n<|think|>\n<turn|>\n<|turn>user\n{ASK}<turn|>\n<|turn>model\n"
GEMMA_SWITCHED = f"<|turn>user\n{ASK}<turn|>\n<|turn>model\n"
GEMMA_SHUT = f"<|turn>user\n{ASK}<turn|>\n<|turn>model\n<|channel>thought\n<channel|>"
# A third chat-template format, invented here because no pick the lineup holds renders anything
# like it. Its closing marker is in neither pair above, so the tail carries no marker this reader
# recognizes, and what tells it apart from the failing pick's own answer is that the key changed
# the tail at all.
THIRD_OPEN = f"<|turn>user\n{ASK}<turn|>\n<|turn>model\n[reasoning]\n"
THIRD_SHUT = f"<|turn>user\n{ASK}<turn|>\n<|turn>model\n[reasoning][/reasoning]\n"


def cell(
    *, constrained: bool, switch: bool, draws: int = 5, deliberated: int = 0
) -> dict[str, object]:
    return {
        "shape": "envelope" if constrained else "plain",
        "constrained": constrained,
        "switch": switch,
        "draws": draws,
        "deliberated": deliberated,
    }


def sample(
    path: Path,
    *,
    plain: str = NATIVE_OPEN,
    switched: str = NATIVE_SHUT,
    cells: list[dict[str, object]] | None = None,
    ask: str = ASK,
) -> Path:
    """Write one tier's sample, defaulting to a pick whose tail closes the thought and whose
    constrained cell held on every draw, the agreeing shape the other cases are read against."""
    written = {
        "model": "cortex",
        "endpoint": "http://127.0.0.1:8080",
        "cap": 256,
        "ask": ask,
        "renderings": [
            {"switch": False, "prompt": plain},
            {"switch": True, "prompt": switched},
        ],
        "cells": cells
        if cells is not None
        else [
            cell(constrained=False, switch=False, deliberated=5),
            cell(constrained=False, switch=True),
            cell(constrained=True, switch=False, deliberated=5),
            cell(constrained=True, switch=True),
        ],
    }
    path.write_text(json.dumps(written), encoding="utf-8")
    return path


def report(path: Path) -> tuple[str, int]:
    lines, code = read(load(path))
    return "\n".join(lines), code


def test_the_tail_is_what_the_template_added_after_the_ask() -> None:
    assert tail(NATIVE_SHUT, ASK) == "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    assert tail(GEMMA_SWITCHED, ASK) == "<turn|>\n<|turn>model\n"


def test_a_rendering_without_the_ask_has_no_tail() -> None:
    """A rendering that does not carry the ask has no tail this reader can place, and none is
    guessed from the end of the prompt."""
    assert tail("<|im_start|>assistant\n<think>\n", ASK) is None


@pytest.mark.parametrize(
    ("rendered", "shut"),
    [
        ("<|im_start|>assistant\n<think>\n\n</think>\n\n", True),
        ("<turn|>\n<|turn>model\n<|channel>thought\n<channel|>", True),
        ("<|im_start|>assistant\n<think>\n", False),
        ("<turn|>\n<|turn>model\n", False),
    ],
)
def test_a_thought_is_closed_only_when_its_last_marker_shuts_it(
    rendered: str, *, shut: bool
) -> None:
    """Both template families, both ways. An opener with no closer leaves the thought open, and a
    tail with no marker at all is the failing pick's own answer to the switch, which is to drop the
    block and add nothing."""
    assert closes(rendered) is shut


def test_the_front_of_a_prompt_cannot_close_a_thought(tmp_path: Path) -> None:
    """This is the case the module exists for. The gemma pair differs by a `<|think|>` system turn
    at the front and ends identically, so a reader comparing whole prompts, or matching a marker
    anywhere in them, would report the failing pick as a holding one."""
    assert closes(GEMMA_OPEN) is False
    assert tail(GEMMA_OPEN, ASK) == tail(GEMMA_SWITCHED, ASK)
    printed, code = report(
        sample(
            tmp_path / "s.json",
            plain=GEMMA_OPEN,
            switched=GEMMA_SWITCHED,
            cells=[
                cell(constrained=True, switch=False, deliberated=5),
                cell(constrained=True, switch=True, deliberated=4),
            ],
        )
    )
    assert "leaves the thought OPEN" in printed
    assert "reads the key" in printed
    assert code == 0


@pytest.mark.parametrize(
    ("rendered", "known"),
    [
        ("<|im_start|>assistant\n<think>\n", True),
        ("<|im_start|>assistant\n<think>\n\n</think>\n\n", True),
        ("<turn|>\n<|turn>model\n<|channel>thought\n<channel|>", True),
        ("<turn|>\n<|turn>model\n", False),
        ("<|turn>model\n[reasoning][/reasoning]\n", False),
    ],
)
def test_a_tail_is_known_when_it_carries_either_familys_marker(
    rendered: str, *, known: bool
) -> None:
    """Either marker of either family is one this reader recognizes. The two unmarked tails are the
    case being separated: one is the failing pick's answer to the switch, the other comes from an
    unrecognized chat-template format."""
    assert marked(rendered) is known


@pytest.mark.parametrize("plain", [THIRD_OPEN, NATIVE_OPEN])
def test_an_unmarked_tail_the_key_changed_publishes_nothing(tmp_path: Path, plain: str) -> None:
    """This is the state the reader will not guess at. A tail carrying no marker of either family
    that also differs from the tail rendered with the key left alone comes from a template this
    module does not recognize, and reading it as an unclosed thought block would publish a
    prediction with no reading behind it. Both directions are covered: an unrecognized format's own
    closing marker, and a template that answered by deleting a marker this reader recognizes."""
    printed, code = report(sample(tmp_path / "s.json", plain=plain, switched=THIRD_SHUT))
    assert "refused: the switched tail carries no marker of either format here" in printed
    assert "answered in an unrecognized format" in printed
    assert repr(tail(THIRD_SHUT, ASK)) in printed
    assert code == 1


def test_the_failing_picks_unmarked_tail_is_read_rather_than_refused(tmp_path: Path) -> None:
    """This is the line the refusal above is drawn against. The failing pick moves a whole system
    turn at the front and leaves the tail byte identical, so an unmarked tail the key never
    changed is the unclosed thought block itself."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            plain=GEMMA_OPEN,
            switched=GEMMA_SWITCHED,
            cells=[
                cell(constrained=True, switch=False, deliberated=5),
                cell(constrained=True, switch=True, deliberated=5),
            ],
        )
    )
    assert "unrecognized format" not in printed
    assert "leaves the thought OPEN" in printed
    assert code == 0


def test_a_closing_tail_beside_a_cell_that_held_is_published(tmp_path: Path) -> None:
    printed, code = report(sample(tmp_path / "s.json"))
    assert "closes the thought" in printed
    assert "agreed: the tail predicts the switch holds under a schema" in printed
    assert code == 0


def test_the_other_familys_closed_thought_reads_the_same_way(tmp_path: Path) -> None:
    """gemma-4 closes a thought with channel markers where the native family closes it with tags,
    and the closing side of that family is the cortex pick: the one tier running the shipped bound
    that pairs a cap, the switch and a schema, and the one with no sampler floor under it."""
    printed, code = report(sample(tmp_path / "s.json", plain=GEMMA_OPEN, switched=GEMMA_SHUT))
    assert "closes the thought" in printed
    assert code == 0


def test_a_closing_tail_beside_a_cell_that_deliberated_is_refused(tmp_path: Path) -> None:
    """One deliberating draw refutes a tail that closed the thought, which is the run a handler
    gating its reasoning rule on the key would produce."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            cells=[
                cell(constrained=True, switch=False, deliberated=5),
                cell(constrained=True, switch=True, deliberated=1),
            ],
        )
    )
    assert "refused: the tail predicts the switch holds under a schema" in printed
    assert "holds on 4 of 5 draws" in printed
    assert code == 1


def test_an_open_tail_beside_a_cell_that_never_deliberated_is_refused(tmp_path: Path) -> None:
    printed, code = report(
        sample(
            tmp_path / "s.json",
            plain=GEMMA_OPEN,
            switched=GEMMA_SWITCHED,
            cells=[
                cell(constrained=True, switch=False, deliberated=5),
                cell(constrained=True, switch=True),
            ],
        )
    )
    assert "refused: the tail predicts the switch does nothing under a schema" in printed
    assert code == 1


def test_a_template_that_never_read_the_key_is_named_as_such(tmp_path: Path) -> None:
    """This is the line to read first when a verdict says the switch holds, since a template that
    rendered the same prompt both ways cannot be why a trace stopped."""
    printed, _ = report(sample(tmp_path / "s.json", plain=NATIVE_SHUT, switched=NATIVE_SHUT))
    assert "the template IGNORES the key" in printed


@pytest.mark.parametrize("switch", [False, True])
def test_a_rendering_that_does_not_carry_the_ask_publishes_nothing(
    tmp_path: Path, *, switch: bool
) -> None:
    someone_elses = "<|im_start|>assistant\n<think>\n"
    printed, code = report(
        sample(
            tmp_path / "s.json",
            plain=someone_elses if not switch else NATIVE_OPEN,
            switched=someone_elses if switch else NATIVE_SHUT,
        )
    )
    assert "does not carry the ask this run sent" in printed
    assert ("sent" if switch else "left alone") in printed
    assert code == 1


def test_a_sample_with_no_constrained_pair_publishes_nothing(tmp_path: Path) -> None:
    """A run configured without the cell the prediction is about publishes nothing, rather than
    making a claim about the tier."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            cells=[
                cell(constrained=False, switch=False, deliberated=5),
                cell(constrained=False, switch=True),
            ],
        )
    )
    assert "does not hold that cell beside its own control" in printed
    assert code == 1


def test_a_control_that_did_not_deliberate_publishes_nothing(tmp_path: Path) -> None:
    """With nothing for the switch to stop, a tier that honours it and one that ignores it look
    the same, so the verdict is not published. The unswitched tail here opens the thought, so the
    prompt is what the refusal names, and the switched tail, which closes it, is not consulted."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            cells=[
                cell(constrained=True, switch=False, deliberated=4),
                cell(constrained=True, switch=True),
            ],
        )
    )
    assert "the control deliberated on 4 of 5 draws" in printed
    assert "invites no thought here" in printed
    assert "renders the thought closed" not in printed
    assert code == 1


def test_a_control_under_a_tail_the_template_closed_names_the_template(tmp_path: Path) -> None:
    """A template that renders the thought closed with the key left alone leaves the control no
    thought to deliberate in. The tail says so in a marker this reader lists, so the refusal names
    the template rather than blaming the prompt."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            plain=NATIVE_SHUT,
            switched=NATIVE_SHUT,
            cells=[
                cell(constrained=True, switch=False),
                cell(constrained=True, switch=True),
            ],
        )
    )
    assert "the control deliberated on 0 of 5 draws" in printed
    assert "renders the thought closed with the key left alone" in printed
    assert "invites no thought" not in printed
    assert code == 1


@pytest.mark.parametrize(
    ("plain", "switched"), [(THIRD_SHUT, THIRD_SHUT), (GEMMA_OPEN, GEMMA_SWITCHED)]
)
def test_a_control_under_an_unmarked_tail_names_both_readings(
    tmp_path: Path, plain: str, switched: str
) -> None:
    """An unmarked tail the key left alone is two templates: the failing pick's, which opens the
    thought with a system turn at the front, and one closing its thought with a marker this reader
    does not list, rendered the same both ways so the tail comparison passes it. The refusal names
    both, since the tail alone cannot separate them, and it is the only line that can."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            plain=plain,
            switched=switched,
            cells=[
                cell(constrained=True, switch=False),
                cell(constrained=True, switch=True),
            ],
        )
    )
    assert "unrecognized format" not in printed
    assert "the control deliberated on 0 of 5 draws" in printed
    assert "a marker this reader does not list" in printed
    assert "invites no thought on this tier" in printed
    assert code == 1


def test_a_cell_drawn_under_the_floor_publishes_nothing(tmp_path: Path) -> None:
    """The default run is one draw, and the cell this turns on splits 4 to 1 on a shipped pick."""
    printed, code = report(
        sample(
            tmp_path / "s.json",
            cells=[
                cell(constrained=True, switch=False, draws=1, deliberated=1),
                cell(constrained=True, switch=True, draws=1),
            ],
        )
    )
    assert f"drawn 1 times against the {switchtail.DRAWS}" in printed
    assert code == 1


def test_every_cell_of_the_run_is_printed_beside_the_rendering(tmp_path: Path) -> None:
    """A refusal names one cell and the report prints all four, because a reader deciding whether
    the rule or this module's vocabulary broke needs the plain shape's verdict too."""
    printed, _ = report(sample(tmp_path / "s.json"))
    assert printed.count("deliberated on") == 4


def test_several_tiers_publish_together_and_the_worst_code_wins(tmp_path: Path) -> None:
    agreeing = load(sample(tmp_path / "held.json"))
    broken = load(
        sample(
            tmp_path / "broken.json",
            cells=[
                cell(constrained=True, switch=False, deliberated=5),
                cell(constrained=True, switch=True, deliberated=5),
            ],
        )
    )
    printed, code = publish([agreeing, broken])
    assert "held.json" in printed
    assert "broken.json" in printed
    assert code == 1
    assert publish([agreeing])[1] == 0


def test_the_command_publishes_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(sample(tmp_path / "s.json"))]) == 0
    assert "agreed:" in capsys.readouterr().out


def test_the_command_exits_one_on_a_prediction_the_measurement_broke(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = sample(
        tmp_path / "s.json",
        cells=[
            cell(constrained=True, switch=False, deliberated=5),
            cell(constrained=True, switch=True, deliberated=5),
        ],
    )
    assert main([str(path)]) == 1
    assert "refused:" in capsys.readouterr().out


def test_the_command_exits_two_on_a_sample_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "missing.json")]) == 2
    assert "switchtail: " in capsys.readouterr().err
