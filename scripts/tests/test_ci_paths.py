import io
import sys

import pytest

import ci_paths

EVERY_RULE_CASES: list[tuple[str, ci_paths.Verdict]] = [
    # ALL: shared gate files affect every toolchain.
    ("justfile", ci_paths.ALL),
    (".python-version", ci_paths.ALL),
    ("proto/body.proto", ci_paths.ALL),
    ("scripts/linecap.py", ci_paths.ALL),
    (".github/workflows/ci.yml", ci_paths.ALL),
    # PYTHON only.
    ("ruff.toml", ci_paths.PYTHON_ONLY),
    ("brain/packages/core/src/cortex_core/ports.py", ci_paths.PYTHON_ONLY),
    # OVERLAY only: the React overlay + its host-only Tauri shell under body/app/.
    ("body/app/src/components/App.tsx", ci_paths.OVERLAY_ONLY),
    # RUST only.
    ("body/crates/core/src/lib.rs", ci_paths.RUST_ONLY),
    # NEITHER: neutral files no toolchain job reads.
    ("docs/index.md", ci_paths.NEITHER),
    (".claude/settings.json", ci_paths.NEITHER),
    (".gitignore", ci_paths.NEITHER),
    (".pre-commit-config.yaml", ci_paths.NEITHER),
    ("LICENSE", ci_paths.NEITHER),
    (".github/dependabot.yml", ci_paths.NEITHER),
    ("README.md", ci_paths.NEITHER),
]


@pytest.mark.parametrize(("path", "verdict"), EVERY_RULE_CASES)
def test_classify_matches_every_rule(path: str, verdict: ci_paths.Verdict) -> None:
    assert ci_paths.classify(path) is verdict


PRECEDENCE_CASES: list[tuple[str, ci_paths.Verdict]] = [
    # A toolchain-tree prefix beats the `.md` suffix rule: files inside a toolchain
    # tree are never assumed inert (tests may read them as fixtures).
    ("brain/README.md", ci_paths.PYTHON_ONLY),
    ("body/README.md", ci_paths.RUST_ONLY),
    ("scripts/README.md", ci_paths.ALL),
    ("proto/README.md", ci_paths.ALL),
    # `body/app/` is the OVERLAY tree and must win over the broader `body/` -> RUST rule
    # (the app crate is excluded from the gated Rust workspace; ADR-0011) and over `.md`.
    ("body/app/src-tauri/Cargo.toml", ci_paths.OVERLAY_ONLY),
    ("body/app/README.md", ci_paths.OVERLAY_ONLY),
    # The workflows prefix beats the `.md`/unmatched fallthroughs.
    (".github/workflows/release.yml", ci_paths.ALL),
    # ...but the dependabot exact rule keeps that one .github file neutral.
    (".github/dependabot.yml", ci_paths.NEITHER),
]


@pytest.mark.parametrize(("path", "verdict"), PRECEDENCE_CASES)
def test_classify_precedence_first_match_wins(path: str, verdict: ci_paths.Verdict) -> None:
    assert ci_paths.classify(path) is verdict


@pytest.mark.parametrize(
    "path",
    [
        "docker-compose.yml",
        "some-new-toplevel.cfg",
        ".github/CODEOWNERS",
        "tools/ruff.toml",  # exact rules never match nested copies
        "justfile.bak",  # exact rules never match longer names
        "protobuf/schema.txt",  # prefix rules require the full directory component
    ],
)
def test_classify_fails_closed_to_all_for_unmatched_paths(path: str) -> None:
    verdict = ci_paths.classify(path)
    assert verdict is ci_paths.DEFAULT
    assert verdict.python
    assert verdict.rust
    assert verdict.overlay


def test_main_empty_input_runs_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == "python=false\nrust=false\noverlay=false\n"
    assert captured.err == ""


def test_main_ignores_blank_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main(["\n", "   \n", ""]) == 0
    captured = capsys.readouterr()
    assert captured.out == "python=false\nrust=false\noverlay=false\n"
    assert captured.err == ""


def test_main_python_only_change(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main(["brain/packages/core/src/foo.py\n"]) == 0
    assert capsys.readouterr().out == "python=true\nrust=false\noverlay=false\n"


def test_main_rust_only_change(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main(["body/crates/core/src/lib.rs\n"]) == 0
    assert capsys.readouterr().out == "python=false\nrust=true\noverlay=false\n"


def test_main_overlay_only_change(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main(["body/app/src/overlay/useOverlay.ts\n"]) == 0
    assert capsys.readouterr().out == "python=false\nrust=false\noverlay=true\n"


def test_main_unions_verdicts_across_paths(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main(["brain/a.py\n", "body/app/x.tsx\n", "body/b.rs\n"]) == 0
    assert capsys.readouterr().out == "python=true\nrust=true\noverlay=true\n"


def test_main_neutral_changes_run_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_paths.main(["docs/adr/ADR-0006-gate-performance.md\n", "LICENSE\n"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "python=false\nrust=false\noverlay=false\n"
    assert captured.err.count("\n") == 2


def test_main_logs_one_verdict_line_per_path_on_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert ci_paths.main(["docs/index.md\n", "\n", "docker-compose.yml\n"]) == 0
    captured = capsys.readouterr()
    assert captured.err == (
        "ci-paths: docs/index.md -> neither\n"
        "ci-paths: docker-compose.yml -> all (fail-closed default)\n"
    )


def test_main_reads_stdin_by_default(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("brain/a.py\njustfile\n"))
    assert ci_paths.main() == 0
    assert capsys.readouterr().out == "python=true\nrust=true\noverlay=true\n"
