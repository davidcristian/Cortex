import json
from pathlib import Path

import pytest

import coverage_gate


def metric(count: int = 10, percent: float = 100.0) -> dict[str, object]:
    return {"count": count, "percent": percent}


def make_totals() -> dict[str, object]:
    return {"lines": metric(), "regions": metric(), "branches": metric()}


def document_with(totals: dict[str, object]) -> dict[str, object]:
    return {"data": [{"totals": totals}], "type": "llvm.coverage.json.export"}


def write_report(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def test_check_passes_when_every_metric_is_full() -> None:
    assert coverage_gate.check(make_totals()) == []


@pytest.mark.parametrize("name", ["lines", "regions", "branches"])
def test_check_fails_each_metric_individually(name: str) -> None:
    totals = make_totals()
    totals[name] = metric(percent=97.5)
    assert coverage_gate.check(totals) == [f"FAIL {name}: 97.50% (need 100%)"]


def test_check_treats_zero_count_metric_as_satisfied() -> None:
    totals = make_totals()
    totals["branches"] = metric(count=0, percent=0.0)
    assert coverage_gate.check(totals) == []


def test_evaluate_notes_zero_count_metric() -> None:
    totals = make_totals()
    totals["branches"] = metric(count=0, percent=0.0)
    reports = coverage_gate.evaluate(totals)
    assert reports[2] == coverage_gate.MetricReport(
        line="PASS branches: no branches to cover (count 0)", ok=True
    )


@pytest.mark.parametrize(
    ("totals", "message"),
    [
        ([], "totals must be a JSON object, got list"),
        ({"lines": metric()}, "totals has no 'regions' entry"),
        ({**make_totals(), "lines": 5}, "totals.lines must be a JSON object, got int"),
        ({**make_totals(), "lines": {"percent": 100.0}}, "totals.lines.count must be a number"),
        ({**make_totals(), "lines": {"count": 10}}, "totals.lines.percent must be a number"),
        (
            {**make_totals(), "lines": {"count": True, "percent": 100.0}},
            "totals.lines.count must be a number, got bool",
        ),
        (
            {**make_totals(), "lines": {"count": 10, "percent": "100"}},
            "totals.lines.percent must be a number, got str",
        ),
    ],
)
def test_evaluate_rejects_malformed_totals(totals: object, message: str) -> None:
    with pytest.raises(coverage_gate.CoverageReportError, match=message):
        coverage_gate.evaluate(totals)


def test_load_totals_returns_the_totals_object(tmp_path: Path) -> None:
    report = tmp_path / "cov.json"
    write_report(report, document_with(make_totals()))
    assert coverage_gate.load_totals(report) == make_totals()


def test_load_totals_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(coverage_gate.CoverageReportError, match="cannot read coverage report"):
        coverage_gate.load_totals(tmp_path / "absent.json")


def test_load_totals_rejects_invalid_json(tmp_path: Path) -> None:
    report = tmp_path / "cov.json"
    report.write_text("{not json", encoding="utf-8")
    with pytest.raises(coverage_gate.CoverageReportError, match="is not valid JSON"):
        coverage_gate.load_totals(report)


MALFORMED_DOCUMENTS: list[tuple[object, str]] = [
    ([1, 2], "coverage report must be a JSON object, got list"),
    ({}, "coverage report 'data' must be a list"),
    ({"data": {}}, "coverage report 'data' must be a list"),
    ({"data": []}, "coverage report 'data' is empty"),
    ({"data": [7]}, r"data\[0\] must be a JSON object, got int"),
    ({"data": [{}]}, r"data\[0\] has no 'totals' entry"),
]


@pytest.mark.parametrize(("document", "message"), MALFORMED_DOCUMENTS)
def test_load_totals_rejects_malformed_documents(
    tmp_path: Path, document: object, message: str
) -> None:
    report = tmp_path / "cov.json"
    write_report(report, document)
    with pytest.raises(coverage_gate.CoverageReportError, match=message):
        coverage_gate.load_totals(report)


def test_main_passes_on_full_coverage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = tmp_path / "cov.json"
    write_report(report, document_with(make_totals()))
    exit_code = coverage_gate.main([str(report)])
    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        "PASS lines: 100.00%",
        "PASS regions: 100.00%",
        "PASS branches: 100.00%",
    ]


def test_main_fails_on_partial_coverage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    totals = make_totals()
    totals["branches"] = metric(percent=99.9)
    report = tmp_path / "cov.json"
    write_report(report, document_with(totals))
    exit_code = coverage_gate.main([str(report)])
    assert exit_code == 1
    assert capsys.readouterr().out.splitlines() == [
        "PASS lines: 100.00%",
        "PASS regions: 100.00%",
        "FAIL branches: 99.90% (need 100%)",
    ]


def test_main_notes_zero_count_metric(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    totals = make_totals()
    totals["branches"] = metric(count=0, percent=0.0)
    report = tmp_path / "cov.json"
    write_report(report, document_with(totals))
    exit_code = coverage_gate.main([str(report)])
    assert exit_code == 0
    assert "PASS branches: no branches to cover (count 0)" in capsys.readouterr().out


def test_main_reports_malformed_export_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "cov.json"
    write_report(report, [])
    exit_code = coverage_gate.main([str(report)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "coverage gate: coverage report must be a JSON object, got list\n"
