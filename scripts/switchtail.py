"""Check that a tier's rendered prompt still predicts what its constrained cell did.

`brain/packages/inference/tests/test_thinking_switch_live.py` sends one prompt four ways against a
live llama-server and records what `POST /apply-template` renders for each. This reads those
samples and holds the rule two documents state, that a template closing the thought honours the
switch under a `response_format` and one leaving it open does not, against the cells the same run
drew.

    just switch-tail measurements/switch-*.json

Exit 0 published the comparison, 1 refused to, 2 could not read a sample.

ADR-0005 argues the five choices behind this: why the reading is on the prompt tail rather than
the whole rendering, why an unmarked tail needs the unswitched one to tell two tiers apart, why a
control that did not fire is explained off that unswitched tail, why the report names the engine
build and the model file the server reported beside the name the operator typed, and why the
check lives here rather than in the integration-marked probe that no gate runs.
"""

import argparse
import sys
from pathlib import Path
from typing import cast

from switchsamples import Cell, Probe, ProbeError, load

# The two template families in ADR-0004's lineup, each as its (opens, closes) marker pair. The bar
# sits on the other side of the closing marker, so neither member of a pair is a substring of the
# other.
MARKERS: tuple[tuple[str, str], ...] = (
    ("<|channel>thought", "<channel|>"),
    ("<think>", "</think>"),
)
# Minimum draws before a cell's verdict is read as a tier's behaviour: the failing pick's
# constrained cell holds on 1 draw in 5.
DRAWS = 5


def tail(prompt: str, ask: str) -> str | None:
    """What the template appended after the ask, or ``None`` when the prompt lacks the ask.

    Found without a per-pick turn marker: whatever follows the last occurrence of the recorded ask
    is what the template added on the model's behalf.
    """
    _, found, rest = prompt.rpartition(ask)
    return rest if found else None


def marked(rendered: str) -> bool:
    """Whether ``rendered`` carries a thought marker of either family in ``MARKERS``."""
    return any(marker in rendered for pair in MARKERS for marker in pair)


def closes(rendered: str) -> bool:
    """Whether the last thought marker in ``rendered`` closes the thought rather than opening it.

    No marker at all answers "open". Only a tail the switch left unchanged is owed that reading, so
    `_tails` checks `marked` and the unswitched tail before calling this.
    """
    opened = max(rendered.rfind(opener) for opener, _ in MARKERS)
    shut = max(rendered.rfind(closer) for _, closer in MARKERS)
    return shut > opened


def unfired(plain: str) -> str:
    """Why a control that did not fire measures nothing, read off the tail the key left alone.

    Three readings: the template closes the thought whatever the key says, the prompt invites no
    thought on this tier, or a marker this reader does not list closed it, which an unmarked tail
    cannot tell from the second.
    """
    if not marked(plain):
        return (
            "the switch stopped nothing; the tail rendered with the key left alone carries no"
            " marker of either format here, so either this prompt invites no thought on this tier"
            " or the template closed the thought with a marker this reader does not list"
        )
    if closes(plain):
        return (
            "the switch stopped nothing: the template renders the thought closed with the key"
            " left alone, and this run says nothing about the switch on this tier"
        )
    return "this prompt invites no thought here and the switch stopped nothing"


def _tails(probe: Probe, lines: list[str]) -> dict[bool, str] | None:
    """Report both renderings, and return their tails keyed by whether the switch was sent.

    ``None`` when a rendering cannot be placed: it lacks the ask the sample recorded, or the
    switched tail carries no marker either family writes and the switch changed it.
    """
    lines.append("  the rendering, taken after the ask itself:")
    found: dict[bool, str] = {}
    for switch in (False, True):
        read = tail(probe.prompt(switch=switch), probe.ask)
        if read is None:
            lines.append(
                f"  refused: the rendering with the switch {'sent' if switch else 'left alone'}"
                " does not carry the ask this run sent, so it has no tail to read"
            )
            return None
        found[switch] = read
        shut = "closes the thought" if closes(read) else "leaves the thought OPEN"
        lines.append(f"    {'switch' if switch else 'no switch':<9} {read!r}  {shut}")
    plain, switched = probe.prompt(switch=False), probe.prompt(switch=True)
    reads = "reads" if plain != switched else "IGNORES"
    lines.append(f"    the template {reads} the key ({len(plain)} chars against {len(switched)})")
    if not marked(found[True]) and found[True] != found[False]:
        lines.append(
            "  refused: the switched tail carries no marker of either format here and is not the"
            " tail this template renders with the key left alone, so it answered in an"
            " unrecognized format and this reader cannot say whether that thought is closed"
        )
        return None
    return found


def _judged(probe: Probe, plain: str, lines: list[str]) -> Cell | None:
    """The constrained cell the prediction is held against, or ``None`` if it may not be read.

    ``plain`` is the tail rendered with the key left alone, which words the control refusal.
    """
    control, cell = probe.cell(switch=False), probe.cell(switch=True)
    if control is None or cell is None:
        lines.append(
            "  refused: a prediction is about the cell carrying a schema and the switch, and"
            " this sample does not hold that cell beside its own control"
        )
        return None
    if control.deliberated < control.draws:
        lines.append(
            f"  refused: the control deliberated on {control.deliberated} of {control.draws}"
            f" draws, so {unfired(plain)}"
        )
        return None
    drawn = min(control.draws, cell.draws)
    if drawn < DRAWS:
        lines.append(
            f"  refused: the constrained cells were drawn {drawn} times against the {DRAWS}"
            " anything quoted as a tier's behaviour is drawn, and this cell splits 4 to 1 on a"
            " shipped pick"
        )
        return None
    return cell


def read(probe: Probe) -> tuple[list[str], int]:
    """One tier's report and exit code: the rendering, the cells, then the rule over both."""
    lines = [
        f"{probe.path}: {probe.model} at {probe.endpoint}",
        f"  served on {probe.build_info} from {probe.model_path}",
    ]
    found = _tails(probe, lines)
    if found is None:
        return lines, 1
    shut = closes(found[True])
    lines.append("  the cells, as the probe drew them:")
    lines.extend(f"    {cell.rendered()}" for cell in probe.cells)
    cell = _judged(probe, found[False], lines)
    if cell is None:
        return lines, 1
    predicted = "holds" if shut else "does nothing"
    said = f"the tail predicts the switch {predicted} under a schema, and it {cell.verdict}"
    if (cell.deliberated == 0) is shut:
        lines.append(f"  agreed: {said} on {cell.draws} draws")
        return lines, 0
    lines.append(
        f"  refused: {said} on {cell.draws} draws. The rule two documents carry is a set of"
        " readings of one engine's handlers and this tier is not one of them: read the tail"
        " above against the record before quoting either."
    )
    return lines, 1


def publish(probes: list[Probe]) -> tuple[str, int]:
    """Every tier's report, and the worst exit code among them."""
    reports = [read(probe) for probe in probes]
    return "\n".join("\n".join(lines) for lines, _ in reports), max(code for _, code in reports)


def main(argv: list[str] | None = None) -> int:
    """Read the samples, publish or refuse, and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Report what a tier's own chat template rendered for a thinking switch, and hold the"
            " rule that reads its constrained verdict off that rendering to what was measured."
        ),
    )
    parser.add_argument("samples", type=Path, nargs="+", help="one switch-<model>.json per tier")
    args = parser.parse_args(argv)
    try:
        probes = [load(path) for path in cast("list[Path]", args.samples)]
    except ProbeError as err:
        print(f"switchtail: {err}", file=sys.stderr)
        return 2
    report, code = publish(probes)
    print(report)
    return code


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
