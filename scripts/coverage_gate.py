"""Repo gate: require 100% line/region/branch coverage from a cargo-llvm-cov JSON export.

``cargo llvm-cov`` has no ``--fail-under-branches`` flag, so this parses the export
written by ``cargo llvm-cov --json --summary-only`` and checks ``data[0].totals``
itself. Each metric passes only when ``covered == count`` -- the producer-computed
``percent`` is never trusted. A metric whose ``count`` is 0 has nothing to cover and is
treated as satisfied, with a printed note.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple, cast

FULL_PERCENT = 100.0
REQUIRED_METRICS = ("lines", "regions", "branches")


class CoverageReportError(Exception):
    """The coverage export is unreadable, malformed, or missing required data."""


class MetricReport(NamedTuple):
    """Outcome for one coverage metric: a printable line and whether it passed."""

    line: str
    ok: bool


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


def evaluate(totals: object) -> list[MetricReport]:
    """Judge every required metric in a cargo-llvm-cov ``totals`` object."""
    totals_map = _require_dict(totals, "totals")
    reports: list[MetricReport] = []
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
            report = MetricReport(f"PASS {metric}: no {metric} to cover (count 0)", ok=True)
        elif covered == count:
            report = MetricReport(f"PASS {metric}: {FULL_PERCENT:.2f}%", ok=True)
        else:
            percent = covered / count * FULL_PERCENT
            report = MetricReport(
                f"FAIL {metric}: {percent:.2f}% (need {FULL_PERCENT:g}%)", ok=False
            )
        reports.append(report)
    return reports


def check(totals: object) -> list[str]:
    """Return one failure string per metric below 100%; an empty list means the gate passes."""
    return [report.line for report in evaluate(totals) if not report.ok]


def load_totals(report: Path) -> object:
    """Extract ``totals`` from the single ``data`` entry of a cargo-llvm-cov JSON export."""
    try:
        payload: object = json.loads(report.read_bytes())
    except OSError as err:
        msg = f"cannot read coverage report {report}: {err}"
        raise CoverageReportError(msg) from err
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        msg = f"coverage report {report} is not valid JSON: {err}"
        raise CoverageReportError(msg) from err
    document = _require_dict(payload, "coverage report")
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


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print one line per metric and return the process exit code."""
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
    args = parser.parse_args(argv)
    report_path: Path = args.report
    try:
        reports = evaluate(load_totals(report_path))
    except CoverageReportError as err:
        print(f"coverage gate: {err}", file=sys.stderr)
        return 1
    for report in reports:
        print(report.line)
    if all(report.ok for report in reports):
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
