import os
import subprocess
from pathlib import Path

import pytest

import commitlint

# Built from escapes, not literals, so this file passes the dash gate.
EM = "\u2014"
EN = "\u2013"
MINUS = "\u2212"

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


# ── dashes as punctuation ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("line", "label"),
    [
        (f"the cause chained {EM} it fails loud", "an em dash"),
        (f"the cause chained {EN} it fails loud", "an en dash"),
        (f"a 2{EN}4B model, where the range once passed", "an en dash"),
        ("the cause chained -- it fails loud", "a spaced ASCII --"),
    ],
)
def test_dash_as_punctuation_is_flagged(line: str, label: str) -> None:
    (problem,) = commitlint.check_body_lines([line], Path())
    assert label in problem


@pytest.mark.parametrize(
    "line",
    [
        "a 2-4B model fits",  # a range takes a plain hyphen
        f"VRAM is 24 GB {MINUS} ~11 GB",  # minus sign is arithmetic, still legal
        "run cargo build --locked",  # CLI flag
        "the well-formed hyphenated-word case",
        "--locked at the start of a line",
    ],
)
def test_non_punctuation_dashes_pass(line: str) -> None:
    assert commitlint.check_body_lines([line], Path()) == []


# ── volatile references ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("line", "label"),
    [
        ("close out Slice 8.8 in the docs", "slice number"),
        ("per ADR-0025 the ticker fires", "decision-record number"),
        ("update the ROADMAP status block", "roadmap reference"),
        ("this closes assumption 1", "numbered assumption"),
        ("increment 4 lands the adapter", "numbered increment"),
        ("amend gate 3 for the new rule", "numbered gate"),
        ("supersedes decision 7", "numbered decision"),
        ("the audit 3 findings are folded in", "numbered audit"),
    ],
)
def test_volatile_reference_is_flagged(line: str, label: str) -> None:
    (problem,) = commitlint.check_body_lines([line], Path())
    assert label in problem


@pytest.mark.parametrize(
    "line",
    [
        "the overlay gate 100% (79 tests) still holds",  # a coverage figure, not a pointer
        "split the turn into a thin end-to-end slice",  # unnumbered methodology word
        "the decision is recorded in the design doc",  # unnumbered
        "raise the cap to 14 GB",
    ],
)
def test_non_volatile_text_passes(line: str) -> None:
    assert commitlint.check_body_lines([line], Path()) == []


# ── commit hashes ──────────────────────────────────────────────────────────────


def _clean_env() -> dict[str, str]:
    """The ambient environment with git's own variables stripped out.

    This suite runs inside `just check`, which the pre-commit hook runs during a real
    commit, and git exports GIT_DIR (and friends) to its hooks. Inheriting those points
    `git -C tmp_path` at the REAL repository no matter what `-C` says: the fixture's
    `add f.txt` then lands in the in-flight commit's index and the seed commit fails.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- fixed argv into a tmp repo, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=_clean_env(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    _git(tmp_path, "commit", "-qm", "seed")
    return tmp_path


def test_a_resolving_commit_hash_is_flagged(repo: Path) -> None:
    sha = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],  # noqa: S607 -- git on PATH
        capture_output=True,
        text=True,
        check=True,
        env=_clean_env(),
    ).stdout.strip()
    (problem,) = commitlint.check_body_lines([f"revises {sha} for longevity"], repo)
    assert "a rewrite invalidates it" in problem


def test_a_hex_string_that_is_not_a_commit_passes(repo: Path) -> None:
    # Action SHAs, colour codes, and digests are legal: only a real, breakable ref is not.
    assert commitlint.check_body_lines(["pin to deadbeefcafe1234"], repo) == []


def test_commit_exists_is_false_when_git_is_missing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        message = "no git"
        raise OSError(message)

    monkeypatch.setattr(commitlint.subprocess, "run", boom)
    # Cannot disprove the hash without git, so the commit is not blocked.
    assert commitlint.commit_exists("abcdef1", repo) is False


# ── whole-message wiring ───────────────────────────────────────────────────────


def test_main_flags_a_body_dash(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    msg = _write(tmp_path, f"feat: add the thing\n\nIt works {EM} mostly.\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert "em dash" in capsys.readouterr().err


def test_main_flags_a_body_volatile_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg = _write(tmp_path, "feat: add the thing\n\nCloses Slice 9.5 as designed.\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert "slice number" in capsys.readouterr().err


def test_main_flags_a_dash_in_the_subject(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg = _write(tmp_path, f"feat: add the thing {EM} and more\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert "em dash" in capsys.readouterr().err


def test_git_tooling_messages_skip_the_body_rules(tmp_path: Path) -> None:
    # A merge message is git's wording, not the author's; ADR-0025 style rules do not apply.
    msg = _write(tmp_path, f"Merge branch 'x'\n\nSee ADR-0025 {EM} really.\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 0
