"""Fail when a cargo-llvm-cov JSON export shows under 100% line, region or branch coverage."""

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


class CheckResult(NamedTuple):
    """Outcome for one check: a printable line and whether it passed."""

    line: str
    ok: bool


class Producer(NamedTuple):
    """What an export records about the run that wrote it."""

    tool: str
    export_format: str


class Toolchain(NamedTuple):
    """What the coverage step probed before it measured."""

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


def evaluate(totals: object) -> list[CheckResult]:
    """Judge every required metric in a cargo-llvm-cov ``totals`` object."""
    totals_map = _require_dict(totals, "totals")
    results: list[CheckResult] = []
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
            result = CheckResult(f"PASS {metric}: no {metric} to cover (count 0)", ok=True)
        elif covered == count:
            result = CheckResult(f"PASS {metric}: {FULL_PERCENT:.2f}%", ok=True)
        else:
            percent = covered / count * FULL_PERCENT
            result = CheckResult(
                f"FAIL {metric}: {percent:.2f}% (need {FULL_PERCENT:g}%)", ok=False
            )
        results.append(result)
    return results


def attribute(producer: Producer, toolchain: Toolchain) -> list[CheckResult]:
    """Name the run that wrote the export, and refuse one this step did not write."""
    results = [
        CheckResult(
            f"measured by cargo-llvm-cov {producer.tool}, llvm export {producer.export_format}",
            ok=True,
        ),
        CheckResult(f"measured by {toolchain.rustc}", ok=True),
    ]
    if producer.tool not in toolchain.llvm_cov.split():
        results.append(
            CheckResult(
                f"FAIL producer: the export was written by cargo-llvm-cov {producer.tool}, "
                f"but this step ran {toolchain.llvm_cov!r}; "
                f"these are not the numbers it measured",
                ok=False,
            )
        )
    return results


def check(totals: object) -> list[str]:
    """Return one failure string per metric below 100%; an empty list means it passes."""
    return [result.line for result in evaluate(totals) if not result.ok]


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
    """Run the check; print one line per metric and return the process exit code."""
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
        help="`rustc +nightly --version` as the step probed it; passed on into the result",
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
        results = attribute(load_producer(document), toolchain)
        results += evaluate(load_totals(document))
    except CoverageReportError as err:
        print(f"rustcoverage: {err}", file=sys.stderr)
        return 1
    for result in results:
        print(result.line)
    if all(result.ok for result in results):
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
