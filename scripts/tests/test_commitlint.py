import subprocess
from pathlib import Path

import pytest

import commitlint
from gitenv import git_env

# Written as escapes so this file passes dashcheck.
EM = "\u2014"
EN = "\u2013"
MINUS = "\u2212"

CLEAN_HEADERS = [
    "feat: add the thing",
    "fix(brain): wrap redis errors as SessionStoreError",
    "docs: sync the deferral ledger",
    "feat(proto)!: renumber nothing, extend everything",
    "chore: bump pins to 2026.1.14",
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
    msg = _write(tmp_path, "# please enter the commit message\nfeat: add the thing\n")
    assert commitlint.main([msg]) == 0


def test_main_passes_an_empty_message(tmp_path: Path) -> None:
    msg = _write(tmp_path, "")
    assert commitlint.main([msg]) == 0


def test_main_usage_error_without_a_file_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        commitlint.main([])
    assert excinfo.value.code == 2
    assert "usage" in capsys.readouterr().err


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
        "a 2-4B model fits",
        f"VRAM is 24 GB {MINUS} ~11 GB",
        "run cargo build --locked",
        "the well-formed hyphenated-word case",
        "--locked at the start of a line",
    ],
)
def test_non_punctuation_dashes_pass(line: str) -> None:
    assert commitlint.check_body_lines([line], Path()) == []


@pytest.mark.parametrize(
    ("line", "label"),
    [
        ("close out Slice 8.8 in the docs", "slice number"),
        ("per ADR-0025 the ticker fires", "decision-record number"),
        ("update the ROADMAP status block", "roadmap reference"),
        ("this closes assumption 1", "numbered assumption"),
        ("increment 4 lands the adapter", "numbered increment"),
        ("amend gate 3 for the new rule", "numbered `gate`"),
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
        "the overlay gate 100% (79 tests) still holds",
        "split the turn into a thin end-to-end slice",
        "the decision is recorded in the design doc",
        "raise the cap to 14 GB",
    ],
)
def test_non_volatile_text_passes(line: str) -> None:
    assert commitlint.check_body_lines([line], Path()) == []


def _git(repo: Path, *args: str) -> None:
    """Run git in the test repo, with the same environment the check uses."""
    subprocess.run(  # noqa: S603 -- fixed argv into a tmp repo, no shell
        ["git", "-C", str(repo), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=git_env(),
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


def _head_sha(repo: Path) -> str:
    """Return the test repository's HEAD as an abbreviated hash."""
    return subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],  # noqa: S607 -- git on PATH
        capture_output=True,
        text=True,
        check=True,
        env=git_env(),
    ).stdout.strip()


def test_a_resolving_commit_hash_is_flagged(repo: Path) -> None:
    (problem,) = commitlint.check_body_lines([f"revises {_head_sha(repo)} for longevity"], repo)
    assert "a rewrite invalidates it" in problem


def test_a_hex_string_that_is_not_a_commit_passes(repo: Path) -> None:
    assert commitlint.check_body_lines(["pin to deadbeefcafe1234"], repo) == []


def test_an_exported_git_dir_does_not_decide_which_repository_answers(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sha = _head_sha(repo)
    monkeypatch.setenv("GIT_DIR", str(repo / "no-such-git-dir"))
    assert commitlint.commit_exists(sha, repo) is True


def test_commit_exists_is_false_when_git_is_missing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        message = "no git"
        raise OSError(message)

    monkeypatch.setattr(commitlint.subprocess, "run", boom)
    assert commitlint.commit_exists("abcdef1", repo) is False


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
        _LONG_URL,
        f"see {_LONG_URL}",
        "brain/packages/orchestrator/src/cortex_orchestrator/" + "a" * 40 + ".py",
    ],
)
def test_a_line_with_nowhere_to_break_is_exempt(line: str) -> None:
    assert len(line) > commitlint.MAX_BODY_WIDTH
    assert commitlint.check_body_lines(["feat: subject", line], Path()) == []


def test_an_overlong_subject_is_reported_once_as_a_header(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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


_WORD = "alpha"
_FULL = " ".join([_WORD] * 12)


def _body(words: int) -> list[str]:
    whole, rest = divmod(words, 12)
    tail = [" ".join([_WORD] * rest)] if rest else []
    return ["feat: add the thing", "", *[_FULL] * whole, *tail]


def test_a_body_at_the_word_cap_passes() -> None:
    assert commitlint.check_body_lines(_body(commitlint.MAX_BODY_WORDS), Path()) == []


def test_a_body_one_word_over_the_cap_is_flagged() -> None:
    (problem,) = commitlint.check_body_lines(_body(commitlint.MAX_BODY_WORDS + 1), Path())
    assert problem == "body is 51 words; AGENTS.md caps it at 50"


def test_the_subject_does_not_count_toward_the_word_cap() -> None:
    lines = _body(commitlint.MAX_BODY_WORDS)
    lines[0] = "feat: add the thing that a few more words describe"
    assert commitlint.check_body_lines(lines, Path()) == []


def test_a_fenced_table_does_not_count_toward_the_word_cap() -> None:
    lines = [*_body(12), "```", *[_FULL] * 6, "```"]
    assert commitlint.check_body_lines(lines, Path()) == []


def test_a_prompted_paste_does_not_count_toward_the_word_cap() -> None:
    paste = f"$ echo {_FULL} {_FULL} {_FULL} {_FULL}"
    assert commitlint.check_body_lines([*_body(12), paste], Path()) == []


def test_main_flags_a_body_over_the_word_cap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg = _write(tmp_path, "\n".join(_body(commitlint.MAX_BODY_WORDS + 1)) + "\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert "caps it at 50" in capsys.readouterr().err


_COMMAND = (
    "docker compose --project-directory . -f docker/docker-compose.yml "
    "-f docker/docker-compose.gpu.yml up -d"
)
_FOOTER = (
    "BREAKING CHANGE: the capture request field is renamed, so every client must be "
    "regenerated from the proto before it connects"
)


def test_a_fenced_line_past_the_wrap_is_exempt() -> None:
    assert len(_COMMAND) > commitlint.MAX_BODY_WIDTH
    assert commitlint.check_widths(["feat: subject", "```", _COMMAND, "```"]) == []


@pytest.mark.parametrize("fence", ["```", "~~~", "```bash", "    ```"])
def test_every_fence_form_opens_and_closes_a_block(fence: str) -> None:
    assert commitlint.check_widths(["feat: subject", fence, _COMMAND, fence]) == []


def test_prose_after_a_closed_fence_is_still_flagged() -> None:
    lines = ["feat: subject", "```", _COMMAND, "```", _OVER]
    (problem,) = commitlint.check_widths(lines)
    assert "line 5 is 73 chars" in problem


def test_an_unclosed_fence_is_itself_a_violation() -> None:
    (problem,) = commitlint.check_widths(["feat: subject", "```", _COMMAND])
    assert "line 2 opens a code fence nothing closes" in problem


def test_a_paste_that_prints_a_fence_of_its_own_is_one_block() -> None:
    lines = ["feat: subject", "````", "```bash", _COMMAND, "```", "````"]
    assert commitlint.check_widths(lines) == []


def test_prose_after_a_nested_paste_is_measured_again() -> None:
    lines = ["feat: subject", "````", "```", _COMMAND, "```", "````", _OVER]
    (problem,) = commitlint.check_widths(lines)
    assert "line 7 is 73 chars" in problem


def test_a_prompted_paste_is_exempt() -> None:
    assert commitlint.check_widths(["feat: subject", f"    $ {_COMMAND}"]) == []


def test_the_line_after_a_prompted_paste_is_measured_again() -> None:
    (problem,) = commitlint.check_widths(["feat: subject", f"$ {_COMMAND}", _OVER])
    assert "line 3 is 73 chars" in problem


@pytest.mark.parametrize(
    "line",
    [
        f"    {_OVER}",
        f"\t{_OVER}",
        f"  $x = {_OVER}",
    ],
)
def test_an_indent_alone_is_not_a_paste(line: str) -> None:
    (problem,) = commitlint.check_widths(["feat: subject", line])
    assert f"is {len(line)} chars" in problem


def test_a_breaking_change_footer_wraps_like_any_other_prose() -> None:
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


def test_main_passes_a_message_with_a_fenced_command(tmp_path: Path) -> None:
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
    assert commitlint.check_body_lines(lines, Path()) == []


@pytest.mark.parametrize("dash", [EM, EN])
def test_a_unicode_dash_inside_a_paste_is_exempt_too(dash: str) -> None:
    lines = ["feat: subject", "```", f"error: expected {dash} found nothing", "```"]
    assert commitlint.check_body_lines(lines, Path()) == []


@pytest.mark.parametrize(
    "lines",
    [
        ["feat: subject", _SEPARATOR],
        ["feat: subject", "```", _SEPARATOR, "```", _SEPARATOR],
        ["feat: subject", f"$ {_SEPARATOR}", _SEPARATOR],
    ],
)
def test_the_same_separator_outside_a_paste_still_fails(lines: list[str]) -> None:
    (problem,) = commitlint.check_body_lines(lines, Path())
    assert "a spaced ASCII --" in problem


def test_a_dash_in_the_subject_is_never_pasted() -> None:
    lines = [f"feat: add the thing {EM} and more", "```", _SEPARATOR, "```"]
    (problem,) = commitlint.check_body_lines(lines, Path())
    assert "an em dash" in problem


def test_an_unclosed_fence_is_still_reported_beside_the_prose_rules() -> None:
    problems = commitlint.check_body_lines(["feat: subject", "```", _SEPARATOR], Path())
    assert len(problems) == 1
    assert "opens a code fence nothing closes" in problems[0]


def test_a_volatile_reference_inside_a_paste_is_still_flagged() -> None:
    lines = ["docs: quote the record", "```", "grep -n 'ADR-0026' docs/adr/*.md", "```"]
    (problem,) = commitlint.check_body_lines(lines, Path())
    assert "decision-record number" in problem


def test_a_resolving_hash_inside_a_paste_is_still_flagged(repo: Path) -> None:
    lines = ["docs: quote the record", "```", f"git show {_head_sha(repo)}", "```"]
    (problem,) = commitlint.check_body_lines(lines, repo)
    assert "a rewrite invalidates it" in problem


def test_main_passes_a_message_whose_fenced_paste_contains_a_separator(tmp_path: Path) -> None:
    msg = _write(tmp_path, f"docs: record the run\n\nThe command is:\n\n```\n{_SEPARATOR}\n```\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 0


def test_classify_lines_marks_a_fence_and_its_contents() -> None:
    classified, opened_at = commitlint.classify_lines(["feat: subject", "```", _SEPARATOR, "```"])
    assert opened_at is None
    assert [line.pasted for line in classified] == [False, True, True, True]


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
    msg = _write(tmp_path, f"Merge branch 'x'\n\nSee ADR-0025 {EM} really.\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 0


_TABLE = """# Rules

| Do not write | Write instead |
| --- | --- |
| gate, gates | check |
| in force | current |
"""


@pytest.fixture
def rules(tmp_path: Path) -> Path:
    path = tmp_path / "AGENTS.md"
    path.write_text(_TABLE, encoding="utf-8")
    return path


def test_a_banned_word_in_the_subject_is_flagged(rules: Path) -> None:
    (problem,) = commitlint.check_words(["feat: widen the gate"], rules)
    assert problem == 'line 1 uses the banned word "gate"; AGENTS.md gives a plain replacement'


def test_a_banned_phrase_split_across_two_body_lines_is_flagged_once(rules: Path) -> None:
    lines = ["feat: x", "", "The rule is in", "force from today."]
    (problem,) = commitlint.check_words(lines, rules)
    assert 'line 3 uses the banned word "in force"' in problem


def test_a_banned_word_inside_a_paste_is_exempt(rules: Path) -> None:
    lines = ["feat: x", "", "```", "gate", "```", "$ gates --all"]
    assert commitlint.check_words(lines, rules) == []


def test_a_banned_word_in_backticks_is_exempt(rules: Path) -> None:
    assert commitlint.check_words(["feat: x", "", "the `gate` recipe"], rules) == []


def test_a_message_with_no_banned_word_passes(rules: Path) -> None:
    assert commitlint.check_words(["feat: x", "", "the check runs first."], rules) == []


def test_a_table_that_cannot_be_read_blocks_the_commit(tmp_path: Path) -> None:
    (problem,) = commitlint.check_words(["feat: x"], tmp_path / "missing.md")
    assert "that table is what the banned-word rule reads" in problem


def test_main_reads_the_table_in_this_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    msg = _write(tmp_path, "feat: add the thing\n\nThis line is load-bearing.\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 1
    assert 'banned word "load-bearing"' in capsys.readouterr().err


def test_main_passes_a_message_with_no_banned_word(tmp_path: Path) -> None:
    msg = _write(tmp_path, "feat: add the thing\n\nThe check reads the table.\n")
    assert commitlint.main([msg, "--repo", str(tmp_path)]) == 0


def test_a_phrase_is_not_found_across_a_paste(rules: Path) -> None:
    lines = ["feat: x", "", "The rule is in", "```", "a paste", "```", "force of habit."]
    assert commitlint.check_words(lines, rules) == []
