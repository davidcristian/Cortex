import json
from pathlib import Path

import pytest

import coverage_gate

TOOL = "0.8.7"
EXPORT_FORMAT = "3.1.0"
PROBED_TOOL = f"cargo-llvm-cov {TOOL}"
PROBED_RUSTC = "rustc 1.98.0-nightly (4c9d2bfe4 2026-07-01)"


def metric(count: int = 10, covered: int = 10, percent: float = 100.0) -> dict[str, object]:
    return {"count": count, "covered": covered, "percent": percent}


def make_totals() -> dict[str, object]:
    return {"lines": metric(), "regions": metric(), "branches": metric()}


def document_with(totals: dict[str, object]) -> dict[str, object]:
    return {
        "data": [{"totals": totals}],
        "type": "llvm.coverage.json.export",
        "version": EXPORT_FORMAT,
        "cargo_llvm_cov": {"version": TOOL, "manifest_path": "/repo/body/Cargo.toml"},
    }


def write_report(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def report_of(tmp_path: Path, document: object) -> str:
    report = tmp_path / "cov.json"
    write_report(report, document)
    return str(report)


def test_check_passes_when_every_metric_is_full() -> None:
    assert coverage_gate.check(make_totals()) == []


@pytest.mark.parametrize("name", ["lines", "regions", "branches"])
def test_check_fails_each_metric_individually(name: str) -> None:
    totals = make_totals()
    totals[name] = metric(count=40, covered=39)
    assert coverage_gate.check(totals) == [f"FAIL {name}: 97.50% (need 100%)"]


def test_check_ignores_producer_percent_and_gates_on_counts() -> None:
    totals = make_totals()
    totals["lines"] = metric(count=10, covered=3, percent=100.0)
    assert coverage_gate.check(totals) == ["FAIL lines: 30.00% (need 100%)"]


def test_evaluate_rejects_covered_exceeding_count() -> None:
    totals = make_totals()
    totals["regions"] = metric(count=10, covered=11)
    with pytest.raises(
        coverage_gate.CoverageReportError,
        match=r"totals\.regions\.covered \(11\) exceeds count \(10\)",
    ):
        coverage_gate.evaluate(totals)


def test_check_treats_zero_count_metric_as_satisfied() -> None:
    totals = make_totals()
    totals["branches"] = metric(count=0, covered=0, percent=0.0)
    assert coverage_gate.check(totals) == []


def test_evaluate_notes_zero_count_metric() -> None:
    totals = make_totals()
    totals["branches"] = metric(count=0, covered=0, percent=0.0)
    verdicts = coverage_gate.evaluate(totals)
    assert verdicts[2] == coverage_gate.Verdict(
        line="PASS branches: no branches to cover (count 0)", ok=True
    )


@pytest.mark.parametrize(
    ("totals", "message"),
    [
        ([], "totals must be a JSON object, got list"),
        ({"lines": metric()}, "totals has no 'regions' entry"),
        ({**make_totals(), "lines": 5}, "totals.lines must be a JSON object, got int"),
        (
            {**make_totals(), "lines": {"covered": 10}},
            "totals.lines.count must be a non-negative integer, got None",
        ),
        (
            {**make_totals(), "lines": {"count": 10}},
            "totals.lines.covered must be a non-negative integer, got None",
        ),
        (
            {**make_totals(), "lines": {"count": True, "covered": 10}},
            "totals.lines.count must be a non-negative integer, got True",
        ),
        (
            {**make_totals(), "lines": {"count": -1, "covered": 0}},
            "totals.lines.count must be a non-negative integer, got -1",
        ),
        (
            {**make_totals(), "lines": {"count": 10, "covered": "10"}},
            "totals.lines.covered must be a non-negative integer, got '10'",
        ),
        (
            {**make_totals(), "lines": {"count": 10, "covered": 10.0}},
            "totals.lines.covered must be a non-negative integer, got 10.0",
        ),
    ],
)
def test_evaluate_rejects_malformed_totals(totals: object, message: str) -> None:
    with pytest.raises(coverage_gate.CoverageReportError, match=message):
        coverage_gate.evaluate(totals)


def test_load_totals_returns_the_totals_object() -> None:
    assert coverage_gate.load_totals(document_with(make_totals())) == make_totals()


def test_read_document_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(coverage_gate.CoverageReportError, match="cannot read coverage report"):
        coverage_gate.read_document(tmp_path / "absent.json")


def test_read_document_rejects_invalid_json(tmp_path: Path) -> None:
    report = tmp_path / "cov.json"
    report.write_text("{not json", encoding="utf-8")
    with pytest.raises(coverage_gate.CoverageReportError, match="is not valid JSON"):
        coverage_gate.read_document(report)


def test_read_document_rejects_non_utf8_bytes(tmp_path: Path) -> None:
    report = tmp_path / "cov.json"
    report.write_bytes(b"\x80\x81\x82")
    with pytest.raises(coverage_gate.CoverageReportError, match="is not valid JSON"):
        coverage_gate.read_document(report)


def test_read_document_rejects_a_non_object_payload(tmp_path: Path) -> None:
    report = tmp_path / "cov.json"
    write_report(report, [1, 2])
    with pytest.raises(
        coverage_gate.CoverageReportError, match="coverage report must be a JSON object, got list"
    ):
        coverage_gate.read_document(report)


MALFORMED_DOCUMENTS: list[tuple[dict[str, object], str]] = [
    ({}, "coverage report 'data' must be a list"),
    ({"data": {}}, "coverage report 'data' must be a list"),
    ({"data": []}, "coverage report 'data' must contain exactly one entry, got 0"),
    (
        {"data": [{"totals": make_totals()}, {"totals": make_totals()}]},
        "coverage report 'data' must contain exactly one entry, got 2",
    ),
    ({"data": [7]}, r"data\[0\] must be a JSON object, got int"),
    ({"data": [{}]}, r"data\[0\] has no 'totals' entry"),
]


@pytest.mark.parametrize(("document", "message"), MALFORMED_DOCUMENTS)
def test_load_totals_rejects_malformed_documents(document: dict[str, object], message: str) -> None:
    with pytest.raises(coverage_gate.CoverageReportError, match=message):
        coverage_gate.load_totals(document)


def test_load_producer_reads_the_writer_the_export_records() -> None:
    assert coverage_gate.load_producer(document_with(make_totals())) == coverage_gate.Producer(
        tool=TOOL, export_format=EXPORT_FORMAT
    )


MALFORMED_PRODUCERS: list[tuple[dict[str, object], str]] = [
    ({}, "coverage report has no 'cargo_llvm_cov' entry naming the tool that wrote it"),
    (
        {"cargo_llvm_cov": ["0.8.7"]},
        "cargo_llvm_cov must be a JSON object, got list",
    ),
    (
        {"cargo_llvm_cov": {}},
        "cargo_llvm_cov.version must be a non-empty string, got None",
    ),
    (
        {"cargo_llvm_cov": {"version": "  "}},
        "cargo_llvm_cov.version must be a non-empty string, got '  '",
    ),
    (
        {"cargo_llvm_cov": {"version": 87}},
        "cargo_llvm_cov.version must be a non-empty string, got 87",
    ),
    (
        {"cargo_llvm_cov": {"version": TOOL}},
        "coverage report.version must be a non-empty string, got None",
    ),
]


@pytest.mark.parametrize(("document", "message"), MALFORMED_PRODUCERS)
def test_load_producer_refuses_an_export_that_will_not_name_its_writer(
    document: dict[str, object], message: str
) -> None:
    with pytest.raises(coverage_gate.CoverageReportError, match=message):
        coverage_gate.load_producer(document)


def test_attribute_names_the_export_writer_without_any_probe() -> None:
    producer = coverage_gate.Producer(tool=TOOL, export_format=EXPORT_FORMAT)
    verdicts = coverage_gate.attribute(producer, coverage_gate.Toolchain(None, None))
    assert verdicts == [
        coverage_gate.Verdict("measured by cargo-llvm-cov 0.8.7, llvm export 3.1.0", ok=True)
    ]


def test_attribute_relays_the_compiler_the_export_cannot_carry() -> None:
    producer = coverage_gate.Producer(tool=TOOL, export_format=EXPORT_FORMAT)
    verdicts = coverage_gate.attribute(producer, coverage_gate.Toolchain(PROBED_RUSTC, PROBED_TOOL))
    assert [verdict.line for verdict in verdicts[1:]] == [f"measured by {PROBED_RUSTC}"]
    assert all(verdict.ok for verdict in verdicts)


@pytest.mark.parametrize("probed", ["cargo-llvm-cov 0.9.1", "", "0.8.70"])
def test_attribute_fails_an_export_this_step_did_not_write(probed: str) -> None:
    producer = coverage_gate.Producer(tool=TOOL, export_format=EXPORT_FORMAT)
    verdicts = coverage_gate.attribute(producer, coverage_gate.Toolchain(None, probed))
    assert [verdict.ok for verdict in verdicts] == [True, False]
    assert verdicts[1].line == (
        f"FAIL producer: the export was written by cargo-llvm-cov {TOOL}, "
        f"but this step ran {probed!r}; these are not the numbers it measured"
    )


def test_main_passes_on_full_coverage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = coverage_gate.main(
        [
            report_of(tmp_path, document_with(make_totals())),
            "--rustc",
            PROBED_RUSTC,
            "--llvm-cov",
            PROBED_TOOL,
        ]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        "measured by cargo-llvm-cov 0.8.7, llvm export 3.1.0",
        f"measured by {PROBED_RUSTC}",
        "PASS lines: 100.00%",
        "PASS regions: 100.00%",
        "PASS branches: 100.00%",
    ]


def test_main_fails_on_partial_coverage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    totals = make_totals()
    totals["branches"] = metric(count=1000, covered=999)
    exit_code = coverage_gate.main([report_of(tmp_path, document_with(totals))])
    assert exit_code == 1
    assert capsys.readouterr().out.splitlines() == [
        "measured by cargo-llvm-cov 0.8.7, llvm export 3.1.0",
        "PASS lines: 100.00%",
        "PASS regions: 100.00%",
        "FAIL branches: 99.90% (need 100%)",
    ]


def test_main_fails_a_stale_export_even_at_full_coverage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = coverage_gate.main(
        [
            report_of(tmp_path, document_with(make_totals())),
            "--llvm-cov",
            "cargo-llvm-cov 0.9.1",
        ]
    )
    assert exit_code == 1
    out = capsys.readouterr().out.splitlines()
    assert out[1].startswith("FAIL producer: the export was written by cargo-llvm-cov 0.8.7")
    assert out[2:] == ["PASS lines: 100.00%", "PASS regions: 100.00%", "PASS branches: 100.00%"]


def test_main_notes_zero_count_metric(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    totals = make_totals()
    totals["branches"] = metric(count=0, covered=0, percent=0.0)
    exit_code = coverage_gate.main([report_of(tmp_path, document_with(totals))])
    assert exit_code == 0
    assert "PASS branches: no branches to cover (count 0)" in capsys.readouterr().out


def test_main_reports_malformed_export_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = coverage_gate.main([report_of(tmp_path, [])])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "coverage gate: coverage report must be a JSON object, got list\n"


def test_main_reports_non_utf8_export_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "cov.json"
    report.write_bytes(b'{"data": [\xff\xfd]}')
    exit_code = coverage_gate.main([str(report)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"coverage gate: coverage report {report} is not valid JSON: ")
    assert captured.err.count("\n") == 1
