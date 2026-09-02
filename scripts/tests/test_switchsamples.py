import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from switchsamples import Cell, ProbeError, load

# The ask a run records sending, shortened here. What matters to this reader is that the same
# string appears in both renderings, since the tail is what follows the last of it.
ASK = "What does each of them pay?"
# What the server this format was validated against reported of itself on `GET /props`.
BUILD = "b10680-d7bd3bfca"
MODEL_PATH = "/models/unsloth/Qwen3.5-0.8B-GGUF/Qwen3.5-0.8B-Q8_0.gguf"
# The two chat-template families in ADR-0004's lineup, as they rendered on `b10666-4e97ac86e`.
NATIVE_OPEN = f"<|im_start|>user\n{ASK}<|im_end|>\n<|im_start|>assistant\n<think>\n"
NATIVE_SHUT = f"<|im_start|>user\n{ASK}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


def sample(
    path: Path,
    *,
    renderings: Sequence[object] | None = None,
    cells: Sequence[object] | None = None,
) -> Path:
    """Write one tier's sample the way the probe writes it, and return its path."""
    written: dict[str, object] = {
        "model": "cortex",
        "endpoint": "http://127.0.0.1:8080",
        "build_info": BUILD,
        "model_path": MODEL_PATH,
        "cap": 256,
        "ask": ASK,
        "renderings": [
            {"switch": False, "prompt": NATIVE_OPEN},
            {"switch": True, "prompt": NATIVE_SHUT},
        ]
        if renderings is None
        else list(renderings),
        "cells": [
            {"shape": "plain", "constrained": False, "switch": False, "draws": 5, "deliberated": 5},
            {"shape": "plain", "constrained": False, "switch": True, "draws": 5, "deliberated": 0},
        ]
        if cells is None
        else list(cells),
    }
    path.write_text(json.dumps(written), encoding="utf-8")
    return path


def rewrite(path: Path, key: str, value: object) -> Path:
    """Replace one field of a written sample, which is the shape drift in the driver arrives in."""
    written = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    written[key] = value
    path.write_text(json.dumps(written), encoding="utf-8")
    return path


def test_a_sample_is_read_as_the_run_that_wrote_it(tmp_path: Path) -> None:
    probe = load(sample(tmp_path / "switch-cortex.json"))
    assert (probe.model, probe.endpoint, probe.ask) == ("cortex", "http://127.0.0.1:8080", ASK)
    assert (probe.build_info, probe.model_path) == (BUILD, MODEL_PATH)
    assert probe.prompt(switch=False) == NATIVE_OPEN
    assert probe.prompt(switch=True) == NATIVE_SHUT
    assert [cell.shape for cell in probe.cells] == ["plain", "plain"]


def test_a_cell_says_what_the_switch_did_in_the_probes_own_three_words() -> None:
    held = Cell("envelope", constrained=True, switch=True, draws=5, deliberated=0)
    dead = Cell("envelope", constrained=True, switch=True, draws=5, deliberated=5)
    split = Cell("envelope", constrained=True, switch=True, draws=5, deliberated=4)
    assert (held.verdict, dead.verdict) == ("holds", "does nothing")
    assert split.verdict == "holds on 1 of 5 draws"


def test_a_cells_line_names_its_shape_and_how_it_was_sent() -> None:
    """The rendered line names the shape and how the request was sent, so a reader can compare it
    against the rendering printed above it."""
    line = Cell("envelope", constrained=True, switch=True, draws=5, deliberated=4).rendered()
    assert "envelope" in line
    assert "switch" in line
    assert "deliberated on 4 of 5" in line
    assert "the switch holds on 1 of 5 draws" in line


def test_only_the_arm_that_sent_the_switch_is_reported_as_a_verdict_about_it() -> None:
    """The arm that sent no switch is reported as a control rather than as a verdict on the switch.
    A line reading "the switch does nothing" beside a request that sent none would report on
    something the run never measured."""
    fired = Cell("plain", constrained=False, switch=False, draws=5, deliberated=5).rendered()
    quiet = Cell("plain", constrained=False, switch=False, draws=5, deliberated=4).rendered()
    assert fired.endswith("the control fired")
    assert quiet.endswith("the control did NOT fire on every draw")


def test_the_constrained_cell_is_found_by_the_samples_own_flags(tmp_path: Path) -> None:
    """The cell is found by the sample's own flags rather than by a shape name, because the two
    trees agree on `constrained` and not on the word `envelope`."""
    probe = load(
        sample(
            tmp_path / "s.json",
            cells=[
                {
                    "shape": "whatever",
                    "constrained": True,
                    "switch": True,
                    "draws": 5,
                    "deliberated": 4,
                },
            ],
        )
    )
    found = probe.cell(switch=True)
    assert found is not None
    assert found.deliberated == 4
    assert probe.cell(switch=False) is None


def test_two_cells_claiming_one_placement_are_no_cell_at_all(tmp_path: Path) -> None:
    """A sample holding two cells at the judged placement publishes none rather than picking the
    first, since nothing distinguishes them."""
    row: dict[str, object] = {
        "shape": "envelope",
        "constrained": True,
        "switch": True,
        "draws": 5,
        "deliberated": 0,
    }
    probe = load(sample(tmp_path / "s.json", cells=[row, dict(row)]))
    assert probe.cell(switch=True) is None


def test_a_file_that_is_not_there_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="unreadable sample"):
        load(tmp_path / "missing.json")


def test_text_that_is_not_json_is_refused_by_name(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ProbeError, match="unreadable sample"):
        load(path)


def test_a_sample_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ProbeError, match="a sample is a JSON object"):
        load(path)


@pytest.mark.parametrize("key", ["model", "endpoint", "build_info", "model_path", "ask"])
def test_a_missing_string_field_is_refused_by_its_own_name(tmp_path: Path, key: str) -> None:
    """A field that is missing or is not a string raises under its own name. The driver that writes
    these samples has no suite of its own, so a field it stopped writing has to fail here rather
    than fall back to a default."""
    with pytest.raises(ProbeError, match=f"{key} is missing or is not a string"):
        load(rewrite(sample(tmp_path / "s.json"), key, 17))


def test_renderings_that_are_not_a_list_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="renderings is missing or is not a list"):
        load(rewrite(sample(tmp_path / "s.json"), "renderings", "both of them"))


def test_an_empty_list_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="cells is empty"):
        load(sample(tmp_path / "s.json", cells=[]))


def test_a_rendering_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="an entry of renderings is not a JSON object"):
        load(sample(tmp_path / "s.json", renderings=["a prompt"]))


def test_a_rendering_with_no_switch_flag_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="switch is missing or is not a boolean"):
        load(sample(tmp_path / "s.json", renderings=[{"prompt": NATIVE_OPEN}]))


def test_one_prompt_is_not_a_run_of_this_probe(tmp_path: Path) -> None:
    """The probe takes two renderings, one with the switch and one without, so a sample carrying a
    single rendering raises as malformed."""
    with pytest.raises(ProbeError, match="one prompt with the switch and one without"):
        load(sample(tmp_path / "s.json", renderings=[{"switch": True, "prompt": NATIVE_SHUT}]))


def test_two_renderings_taken_the_same_way_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="one prompt with the switch and one without"):
        load(
            sample(
                tmp_path / "s.json",
                renderings=[
                    {"switch": True, "prompt": NATIVE_SHUT},
                    {"switch": True, "prompt": NATIVE_OPEN},
                ],
            )
        )


@pytest.mark.parametrize("drawn", ["five", True, -1])
def test_a_draw_count_that_is_not_a_count_is_refused(tmp_path: Path, drawn: object) -> None:
    """A string, a boolean and a negative number each raise. The boolean and the negative would
    otherwise compare against the draw floor and pass or fail on a value that is not a count."""
    cells = [
        {
            "shape": "plain",
            "constrained": False,
            "switch": False,
            "draws": drawn,
            "deliberated": 0,
        },
    ]
    with pytest.raises(ProbeError, match="draws is missing or is not a count"):
        load(sample(tmp_path / "s.json", cells=cells))
