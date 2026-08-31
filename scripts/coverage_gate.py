"""Repo gate: require 100% line/region/branch coverage from a cargo-llvm-cov JSON export.

This is the whole coverage verdict on the Rust body, not the branch half of it.
cargo-llvm-cov has no ``--fail-under-branches`` flag, so branches were always judged here;
``--fail-under-lines`` and ``--fail-under-regions`` were dropped from the measurement because
they exit 1 without printing anything once ``--json --output-path`` diverts the report to a
file, which pre-empted this gate with a mute failure. So this parses the export written by
``cargo llvm-cov --json --summary-only`` and checks ``data[0].totals`` itself. Each metric
passes only when ``covered == count``; the producer-computed ``percent`` is never read.
A metric whose ``count`` is 0 has nothing to cover and is treated as satisfied, with a
printed note.

The verdict also names the toolchain that produced the numbers, because the coverage step
runs on an unpinned nightly and an unpinned cargo-llvm-cov (ADR-0002), so a red run has to
be readable against the versions that measured it. Two sources, both required. The export
records its own writer in ``cargo_llvm_cov.version``, and a report that does not carry that
record is refused. The compiler is nowhere in the export, so the step relays what it probed through
``--rustc``, and relays ``--llvm-cov`` too, where it is checked against the export's own
record rather than merely echoed. Disagreement means the numbers being judged are not the
ones this run measured.

Both relays are required arguments, not optional ones. The producer cross-check is the half of
the attribution that can actually fail, so an optional flag would let a recipe edit delete the
check while every remaining line still printed green. A run that omits either probe now exits
on argparse's own usage error instead, having printed no verdict at all.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple, cast

FULL_PERCENT = 100.0
REQUIRED_METRICS = ("lines", "regions", "branches")
PRODUCER_KEY = "cargo_llvm_cov"


class CoverageReportError(Exception):
    """The coverage export is unreadable, malformed, or missing required data."""


class Verdict(NamedTuple):
    """Outcome for one check: a printable line and whether it passed."""

    line: str
    ok: bool


class Producer(NamedTuple):
    """What an export records about the run that wrote it."""

    tool: str
    export_format: str


class Toolchain(NamedTuple):
    """What the coverage step probed before it measured. Both halves are mandatory."""

    rustc: str
    llvm_cov: str


def _require_dict(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = f"{context} must be a JSON object, got {type(value).__name__}"
        raise CoverageReportError(msg)
    return cast("dict[str, object]", value)


def _require_count(entry: dict[str, object], key: str, context: str) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        msg = f"{context}.{key} must be a non-negative integer, got {value!r}"
        raise CoverageReportError(msg)
    return value


def _require_version(entry: dict[str, object], key: str, context: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"{context}.{key} must be a non-empty string, got {value!r}"
        raise CoverageReportError(msg)
    return value


def evaluate(totals: object) -> list[Verdict]:
    """Judge every required metric in a cargo-llvm-cov ``totals`` object."""
    totals_map = _require_dict(totals, "totals")
    verdicts: list[Verdict] = []
    for metric in REQUIRED_METRICS:
        if metric not in totals_map:
            msg = f"totals has no {metric!r} entry"
            raise CoverageReportError(msg)
        entry = _require_dict(totals_map[metric], f"totals.{metric}")
        count = _require_count(entry, "count", f"totals.{metric}")
        covered = _require_count(entry, "covered", f"totals.{metric}")
        if covered > count:
            msg = f"totals.{metric}.covered ({covered}) exceeds count ({count})"
            raise CoverageReportError(msg)
        if count == 0:
            verdict = Verdict(f"PASS {metric}: no {metric} to cover (count 0)", ok=True)
        elif covered == count:
            verdict = Verdict(f"PASS {metric}: {FULL_PERCENT:.2f}%", ok=True)
        else:
            percent = covered / count * FULL_PERCENT
            verdict = Verdict(f"FAIL {metric}: {percent:.2f}% (need {FULL_PERCENT:g}%)", ok=False)
        verdicts.append(verdict)
    return verdicts


def attribute(producer: Producer, toolchain: Toolchain) -> list[Verdict]:
    """Name the run that wrote the export, and refuse one this step did not write."""
    verdicts = [
        Verdict(
            f"measured by cargo-llvm-cov {producer.tool}, llvm export {producer.export_format}",
            ok=True,
        ),
        Verdict(f"measured by {toolchain.rustc}", ok=True),
    ]
    if producer.tool not in toolchain.llvm_cov.split():
        verdicts.append(
            Verdict(
                f"FAIL producer: the export was written by cargo-llvm-cov {producer.tool}, "
                f"but this step ran {toolchain.llvm_cov!r}; "
                f"these are not the numbers it measured",
                ok=False,
            )
        )
    return verdicts


def check(totals: object) -> list[str]:
    """Return one failure string per metric below 100%; an empty list means the gate passes."""
    return [verdict.line for verdict in evaluate(totals) if not verdict.ok]


def read_document(report: Path) -> dict[str, object]:
    """Parse a cargo-llvm-cov JSON export into its top-level object."""
    try:
        payload: object = json.loads(report.read_bytes())
    except OSError as err:
        msg = f"cannot read coverage report {report}: {err}"
        raise CoverageReportError(msg) from err
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        msg = f"coverage report {report} is not valid JSON: {err}"
        raise CoverageReportError(msg) from err
    return _require_dict(payload, "coverage report")


def load_totals(document: dict[str, object]) -> object:
    """Extract ``totals`` from the single ``data`` entry of a cargo-llvm-cov JSON export."""
    data = document.get("data")
    if not isinstance(data, list):
        msg = "coverage report 'data' must be a list"
        raise CoverageReportError(msg)
    entries = cast("list[object]", data)
    if len(entries) != 1:
        msg = f"coverage report 'data' must contain exactly one entry, got {len(entries)}"
        raise CoverageReportError(msg)
    first = _require_dict(entries[0], "data[0]")
    if "totals" not in first:
        msg = "data[0] has no 'totals' entry"
        raise CoverageReportError(msg)
    return first["totals"]


def load_producer(document: dict[str, object]) -> Producer:
    """Extract what a cargo-llvm-cov JSON export records about the run that wrote it."""
    if PRODUCER_KEY not in document:
        msg = f"coverage report has no {PRODUCER_KEY!r} entry naming the tool that wrote it"
        raise CoverageReportError(msg)
    block = _require_dict(document[PRODUCER_KEY], PRODUCER_KEY)
    return Producer(
        tool=_require_version(block, "version", PRODUCER_KEY),
        export_format=_require_version(document, "version", "coverage report"),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print one line per check and return the process exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Fail unless a cargo-llvm-cov JSON export shows 100% line, region, and branch coverage."
        ),
    )
    parser.add_argument(
        "report",
        type=Path,
        help="path to a `cargo llvm-cov --json --summary-only` export file",
    )
    parser.add_argument(
        "--rustc",
        required=True,
        help="`rustc +nightly --version` as the step probed it; relayed into the verdict",
    )
    parser.add_argument(
        "--llvm-cov",
        required=True,
        help="`cargo +nightly llvm-cov --version` as the step probed it; checked against"
        " the version the export records for itself",
    )
    args = parser.parse_args(argv)
    report_path: Path = args.report
    toolchain = Toolchain(rustc=args.rustc, llvm_cov=args.llvm_cov)
    try:
        document = read_document(report_path)
        verdicts = attribute(load_producer(document), toolchain)
        verdicts += evaluate(load_totals(document))
    except CoverageReportError as err:
        print(f"coverage gate: {err}", file=sys.stderr)
        return 1
    for verdict in verdicts:
        print(verdict.line)
    if all(verdict.ok for verdict in verdicts):
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
