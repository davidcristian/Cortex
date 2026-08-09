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


# ── body width ─────────────────────────────────────────────────────────────────

# Exactly 73 characters, all short words, so it had somewhere to break: one of the four real
# lines that reached master while this rule did not exist.
_OVER = "The projector rides the cortex tier's argv from CORTEX_MMPROJ_FILE_CORTEX"
_LONG_URL = "https://example.invalid/" + "x" * 60


def test_a_wrappable_line_past_the_wrap_is_flagged() -> None:
    assert len(_OVER) == 73
    (problem,) = commitlint.check_body_lines(["feat: subject", _OVER], Path())
    assert "line 2 is 73 chars" in problem
    assert "wraps the body at 72" in problem


def test_a_line_exactly_at_the_wrap_passes() -> None:
    line = _OVER[:-1]
    assert len(line) == 72
    assert commitlint.check_body_lines(["feat: subject", line], Path()) == []


@pytest.mark.parametrize(
    "line",
    [
        _LONG_URL,  # one unbreakable token: nowhere to break
        f"see {_LONG_URL}",  # a URL past the wrap on its own, with a word beside it
        "brain/packages/orchestrator/src/cortex_orchestrator/" + "a" * 40 + ".py",
    ],
)
def test_a_line_with_nowhere_to_break_is_exempt(line: str) -> None:
    assert len(line) > commitlint.MAX_BODY_WIDTH
    assert commitlint.check_body_lines(["feat: subject", line], Path()) == []


def test_an_overlong_subject_is_reported_once_as_a_header(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The header owns its own cap and its own sentence; the width rule starts below it, so one
    # long subject is one complaint rather than two.
    msg = _write(tmp_path, f"feat: {'x ' * 40}\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    errors = capsys.readouterr().err.splitlines()
    assert len(errors) == 1
    assert "caps the subject line at 72" in errors[0]


def test_main_flags_a_body_line_past_the_wrap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg = _write(tmp_path, f"feat: add the thing\n\n{_OVER}\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert "wraps the body at 72" in capsys.readouterr().err


# ── the wrap's line-kind exemptions ────────────────────────────────────────────

# 104 characters, longest word 29: a real invocation from the repo's own runbooks, and the
# shape the word-width exemption cannot see, since every word in it fits the wrap.
_COMMAND = (
    "docker compose --project-directory . -f docker/docker-compose.yml "
    "-f docker/docker-compose.gpu.yml up -d"
)
# 124 characters, longest word 11: a footer of short words, which is the sharp case.
_FOOTER = (
    "BREAKING CHANGE: the capture request field is renamed, so every client must be "
    "regenerated from the proto before it connects"
)


def test_a_fenced_line_past_the_wrap_is_exempt() -> None:
    assert len(_COMMAND) > commitlint.MAX_BODY_WIDTH
    assert commitlint.check_widths(["feat: subject", "```", _COMMAND, "```"]) == []


@pytest.mark.parametrize("fence", ["```", "~~~", "```bash", "    ```"])
def test_every_fence_spelling_opens_and_closes_a_block(fence: str) -> None:
    # An info string still opens a block, and either fence character does; a fence indented
    # inside a list item is still a fence.
    assert commitlint.check_widths(["feat: subject", fence, _COMMAND, fence]) == []


def test_prose_after_a_closed_fence_is_still_flagged() -> None:
    # The leak that matters: an exemption that outlives its block is the gate not holding.
    lines = ["feat: subject", "```", _COMMAND, "```", _OVER]
    (problem,) = commitlint.check_widths(lines)
    assert "line 5 is 73 chars" in problem


def test_an_unclosed_fence_is_itself_a_violation() -> None:
    # Otherwise one stray fence exempts every line after it, silently and forever.
    (problem,) = commitlint.check_widths(["feat: subject", "```", _COMMAND])
    assert "line 2 opens a code fence nothing closes" in problem


def test_a_prompted_paste_is_exempt() -> None:
    assert commitlint.check_widths(["feat: subject", f"    $ {_COMMAND}"]) == []


def test_the_line_after_a_prompted_paste_is_measured_again() -> None:
    # The prompt marks its own line, not the rest of the message.
    (problem,) = commitlint.check_widths(["feat: subject", f"$ {_COMMAND}", _OVER])
    assert "line 3 is 73 chars" in problem


@pytest.mark.parametrize(
    "line",
    [
        f"    {_OVER}",  # a nested bullet's continuation: prose, and this repo's history has 9
        f"\t{_OVER}",
        f"  $x = {_OVER}",  # a dollar that is not a prompt
    ],
)
def test_an_indent_alone_is_not_a_paste(line: str) -> None:
    (problem,) = commitlint.check_widths(["feat: subject", line])
    assert f"is {len(line)} chars" in problem


def test_a_breaking_change_footer_wraps_like_any_other_prose() -> None:
    # Decided rather than exempted: the footer is a machine-read token over a prose value,
    # and the parser that reads it allows newlines in that value, so wrapping costs nothing.
    assert len(_FOOTER) == 124
    (problem,) = commitlint.check_widths(["feat(proto)!: rename the capture field", _FOOTER])
    assert "line 2 is 124 chars" in problem


def test_a_wrapped_breaking_change_footer_passes() -> None:
    lines = [
        "feat(proto)!: rename the capture field",
        "",
        "BREAKING CHANGE: the capture request field is renamed, so every",
        "client must be regenerated from the proto before it connects.",
    ]
    assert commitlint.check_widths(lines) == []


def test_main_passes_a_message_carrying_a_fenced_command(tmp_path: Path) -> None:
    msg = _write(
        tmp_path, f"docs: record the invocation\n\nBring the stack up:\n\n```\n{_COMMAND}\n```\n"
    )
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 0


def test_main_fails_a_message_whose_fence_is_left_open(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg = _write(tmp_path, f"docs: record the invocation\n\n```\n{_COMMAND}\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert "code fence nothing closes" in capsys.readouterr().err


# ── how far the paste exemption reaches ────────────────────────────────────────

# The two shapes this repo's own gate commands carry: cargo's argument separator, which the
# dash ban reads as punctuation, and a hash that really resolves.
_SEPARATOR = "cargo llvm-cov -- --nocapture"


@pytest.mark.parametrize(
    "lines",
    [
        ["feat: subject", "```", _SEPARATOR, "```"],
        ["feat: subject", "~~~bash", _SEPARATOR, "~~~"],
        ["feat: subject", f"    $ {_SEPARATOR}"],
    ],
)
def test_a_separator_inside_a_paste_is_not_punctuation(lines: list[str]) -> None:
    # cargo's own argument separator, which no restructured sentence can remove.
    assert commitlint.check_body_lines(lines, Path()) == []


@pytest.mark.parametrize("dash", [EM, EN])
def test_a_unicode_dash_inside_a_paste_is_exempt_too(dash: str) -> None:
    # Verbatim output can carry one, and altering a paste is the failure the kind exemption
    # exists to prevent; the exemption is keyed on the kind, never on the character.
    lines = ["feat: subject", "```", f"error: expected {dash} found nothing", "```"]
    assert commitlint.check_body_lines(lines, Path()) == []


@pytest.mark.parametrize(
    "lines",
    [
        ["feat: subject", _SEPARATOR],  # never fenced at all
        ["feat: subject", "```", _SEPARATOR, "```", _SEPARATOR],  # after the fence closed
        ["feat: subject", f"$ {_SEPARATOR}", _SEPARATOR],  # the prompt marks its own line
    ],
)
def test_the_same_separator_outside_a_paste_still_fails(lines: list[str]) -> None:
    # An exemption that outlives its block is the gate not holding.
    (problem,) = commitlint.check_body_lines(lines, Path())
    assert "a spaced ASCII --" in problem


def test_a_dash_in_the_subject_is_never_pasted() -> None:
    # Line 1 is the header: the fence toggle starts below it, so no message can exempt its own
    # subject by opening a block. The fenced separator beside it is exempt, so this is one
    # complaint rather than two.
    lines = [f"feat: add the thing {EM} and more", "```", _SEPARATOR, "```"]
    (problem,) = commitlint.check_body_lines(lines, Path())
    assert "an em dash" in problem


def test_an_unclosed_fence_is_still_reported_beside_the_prose_rules() -> None:
    problems = commitlint.check_body_lines(["feat: subject", "```", _SEPARATOR], Path())
    assert len(problems) == 1
    assert "opens a code fence nothing closes" in problems[0]


def test_a_volatile_reference_inside_a_paste_is_still_flagged() -> None:
    # Not exempt, and deliberately: the ban is about the message still reading correctly once
    # the thing it points at moves, which does not care who typed the pointer.
    lines = ["docs: quote the record", "```", "grep -n 'ADR-0026' docs/adr/*.md", "```"]
    (problem,) = commitlint.check_body_lines(lines, Path())
    assert "decision-record number" in problem


def test_a_resolving_hash_inside_a_paste_is_still_flagged(repo: Path) -> None:
    sha = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],  # noqa: S607 -- git on PATH
        capture_output=True,
        text=True,
        check=True,
        env=_clean_env(),
    ).stdout.strip()
    lines = ["docs: quote the record", "```", f"git show {sha}", "```"]
    (problem,) = commitlint.check_body_lines(lines, repo)
    assert "a rewrite invalidates it" in problem


def test_main_passes_a_message_whose_fenced_paste_carries_a_separator(tmp_path: Path) -> None:
    msg = _write(tmp_path, f"docs: record the run\n\nThe gate is:\n\n```\n{_SEPARATOR}\n```\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 0


def test_classify_lines_marks_a_fence_and_its_contents() -> None:
    classified, opened_at = commitlint.classify_lines(["feat: subject", "```", _SEPARATOR, "```"])
    assert opened_at is None
    assert [line.pasted for line in classified] == [False, True, True, True]


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
