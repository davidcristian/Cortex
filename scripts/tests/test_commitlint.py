from pathlib import Path

import pytest

import commitlint

CLEAN_HEADERS = [
    "feat: add the thing",
    "fix(brain): wrap redis errors as SessionStoreError",
    "docs: sync the deferral ledger",
    "feat(proto)!: renumber nothing, extend everything",
    "chore: bump pins to 2026.1.14",  # digits after the colon are fine
]


@pytest.mark.parametrize("header", CLEAN_HEADERS)
def test_clean_headers_pass(header: str) -> None:
    assert commitlint.check_header(header) == []


def test_overlong_header_is_flagged() -> None:
    header = "feat: " + "x" * commitlint.MAX_HEADER_LENGTH
    (problem,) = commitlint.check_header(header)
    assert f"caps the subject line at {commitlint.MAX_HEADER_LENGTH}" in problem


def test_uppercase_subject_is_flagged() -> None:
    (problem,) = commitlint.check_header("feat: Add the thing")
    assert problem == "subject must start lowercase"


def test_trailing_period_is_flagged() -> None:
    (problem,) = commitlint.check_header("feat: add the thing.")
    assert problem == "subject must not end with a period"


def test_all_three_violations_report_together() -> None:
    header = "feat: " + "X" * commitlint.MAX_HEADER_LENGTH + "."
    assert len(commitlint.check_header(header)) == 3


def test_non_conventional_header_passes_silently() -> None:
    # Structure errors are conventional-pre-commit's to report, not this hook's.
    assert commitlint.check_header("Added stuff without a type.") == []


@pytest.mark.parametrize(
    "header",
    ["Merge branch 'master'", "fixup! feat: Original.", "squash! feat: X", "amend! fix: Y"],
)
def test_git_tooling_headers_are_exempt(header: str) -> None:
    assert commitlint.check_header(header) == []


def _write(tmp_path: Path, text: str) -> str:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_main_passes_a_clean_message(tmp_path: Path) -> None:
    msg = _write(tmp_path, "feat: add the thing\n\nBody line.\n")
    assert commitlint.main([msg]) == 0


def test_main_fails_a_violating_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    msg = _write(tmp_path, "feat: Add the thing.\n")
    assert commitlint.main([msg]) == 1
    err = capsys.readouterr().err
    assert "subject must start lowercase" in err
    assert "subject must not end with a period" in err


def test_main_skips_comment_lines(tmp_path: Path) -> None:
    # `git commit` templates put comments first; the header is the first real line.
    msg = _write(tmp_path, "# please enter the commit message\nfeat: add the thing\n")
    assert commitlint.main([msg]) == 0


def test_main_passes_an_empty_message(tmp_path: Path) -> None:
    # git aborts empty commits itself; nothing for this hook to say.
    msg = _write(tmp_path, "")
    assert commitlint.main([msg]) == 0


def test_main_usage_error_without_a_file_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        commitlint.main([])
    assert excinfo.value.code == 2
    assert "usage" in capsys.readouterr().err
