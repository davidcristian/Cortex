"""Whether a tier's rendered prompt still predicts what its constrained cell did."""

import argparse
import sys
from pathlib import Path
from typing import cast

from switchsamples import Cell, Probe, ProbeError, load

MARKERS: tuple[tuple[str, str], ...] = (
    ("<|channel>thought", "<channel|>"),
    ("<think>", "</think>"),
)
# How many draws a cell must carry before its verdict is read as a tier's behaviour. The probe's
# own rule, and its own reason: the constrained cell of the failing pick holds on 1 draw in 5.
DRAWS = 5


def tail(prompt: str, ask: str) -> str | None:
    """What the template appended after the ask itself, or ``None`` when the ask is not in there.

    The generation prompt, found without knowing one per pick turn marker: whatever follows the
    last of the words the driver recorded sending is what the template added on the model's behalf.
    """
    _, found, rest = prompt.rpartition(ask)
    return rest if found else None


def closes(rendered: str) -> bool:
    """Whether the last thought marker in ``rendered`` is a closing one."""
    opened = max(rendered.rfind(opener) for opener, _ in MARKERS)
    shut = max(rendered.rfind(closer) for _, closer in MARKERS)
    return shut > opened


def _tails(probe: Probe, lines: list[str]) -> bool | None:
    """Report both renderings, and answer whether the switched one closes the thought.

    ``None`` is a rendering this reader cannot place: one that does not carry the ask the same
    sample says was sent, and whose tail therefore cannot be found.
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
    return closes(found[True])


def _judged(probe: Probe, lines: list[str]) -> Cell | None:
    """The constrained cell the prediction is held against, if this sample may be read at all."""
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
            " draws, so this prompt invites no thought here and the switch stopped nothing"
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
    """One tier's report and its exit code: the rendering, the cells, then the rule over both."""
    lines = [f"{probe.path}: {probe.model} at {probe.endpoint}"]
    shut = _tails(probe, lines)
    if shut is None:
        return lines, 1
    lines.append("  the cells, as the probe drew them:")
    lines.extend(f"    {cell.rendered()}" for cell in probe.cells)
    cell = _judged(probe, lines)
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
