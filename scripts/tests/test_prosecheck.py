# The autouse fixture below is called by pytest, never by name, which pyright cannot see.
# pyright: reportUnusedFunction=false

import subprocess
from pathlib import Path

import pytest

import bannedwords
import prosecheck
import prosereaders
from gitenv import git_env
from prosecheck import Exemption, Problem

REPO_ROOT = Path(__file__).resolve().parents[2]
EXEMPTIONS = prosecheck.EXEMPTIONS

RULES = """# Rules

Prose here is plain.

| Do not write | Write instead |
| --- | --- |
| gate, gates | check |
| in force | current |
"""
PATTERN = bannedwords.compile_words(["gate", "gates", "in force"])
FENCE = "`" * 3
LONG_DOCSTRING = '"""One.\n\nTwo.\nThree.\nFour.\n"""\n'
LONG_BLOCK = "# one\n# two\n# three\n# four\nx = 1\n"
BANNED_DOCSTRING = '"""A gate.\n\nTwo.\nThree.\nFour.\n"""\n'
DECORATED_TOOL = (
    "\n\n@server.tool()\ndef tool() -> None:\n"
    '    """A gate.\n\n    Two.\n    Three.\n    Four.\n    """\n'
)


@pytest.fixture(autouse=True)
def _without_exemptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prosecheck, "EXEMPTIONS", ())


def _git(root: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["git", "-C", str(root), *args],  # noqa: S607 -- git on PATH
        check=True,
        capture_output=True,
        env=git_env(),
    )


def _write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _write(tmp_path, "AGENTS.md", RULES)
    return tmp_path


def _check(name: str, text: str) -> list[str]:
    reader = prosereaders.reader_for(name)
    assert reader is not None
    return [
        problem.message for problem in prosecheck.check_prose(Path(name), reader(text), PATTERN)
    ]


def test_markdown_lines_leave_out_fenced_blocks() -> None:
    text = f"one\n{FENCE}sh\ngate\n{FENCE}\ntwo"
    assert prosereaders.markdown_lines(text) == [(1, "one"), (5, "two")]


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("README.md", "A gate.\n"),
        ("a.py", "x = 1  # a gate\n"),
        ("a.py", '"""A gate."""\n'),
        ("a.pyi", "# a gate\n"),
        ("a.rs", "// a gate\n"),
        ("a.ts", "/* a gate */\n"),
        ("a.tsx", "// a gate\n"),
        ("a.css", "/* a gate */\n"),
        ("a.proto", "// a gate\n"),
        ("ci.yml", "# a gate\n"),
        ("x.yaml", "# a gate\n"),
        ("pyproject.toml", "# a gate\n"),
        ("run.sh", "# a gate\n"),
        ("probe.conf", "# a gate\n"),
        ("justfile", "# a gate\n"),
        (".gitignore", "# a gate\n"),
        (".dockerignore", "# a gate\n"),
        ("Dockerfile", "# a gate\n"),
        ("Dockerfile.modelhost", "# a gate\n"),
        ("init.sql", "-- a gate\n"),
    ],
)
def test_every_checked_file_type_is_searched(name: str, text: str) -> None:
    assert _check(name, text) == ['banned word "gate"']


@pytest.mark.parametrize("name", ["logo.png", "data.json", "index.html", "LICENSE"])
def test_other_file_types_are_not_checked(name: str) -> None:
    assert prosereaders.reader_for(name) is None


def test_string_literals_and_code_are_not_searched() -> None:
    assert _check("a.py", 'gate = "a gate"\n') == []


def test_long_docstrings_and_comment_blocks_are_reported() -> None:
    assert _check("a.py", LONG_DOCSTRING + LONG_BLOCK) == [
        "docstring has 4 lines, at most 3",
        "comment block has 4 lines, at most 3",
    ]


def test_three_lines_are_allowed() -> None:
    assert _check("a.py", '"""One.\nTwo.\nThree.\n"""\n# one\n# two\n# three\nx = 1\n') == []


def test_problems_are_sorted_by_line() -> None:
    prose = prosereaders.reader_for("a.py")
    assert prose is not None
    problems = prosecheck.check_prose(Path("a.py"), prose("# gate\n" + LONG_DOCSTRING), PATTERN)
    assert [problem.line for problem in problems] == [1, 2]


def test_exempt_lines_are_not_searched_for_words() -> None:
    reader = prosereaders.reader_for("AGENTS.md")
    assert reader is not None
    prose = reader("a gate\nthe gates\nin\nforce\n")
    problems = prosecheck.check_prose(Path("AGENTS.md"), prose, PATTERN, range(2, 4))
    assert problems == [Problem(Path("AGENTS.md"), 1, prosecheck.BANNED, 'banned word "gate"')]


def test_scan_reads_the_tree_minus_ignored_and_generated_files(repo: Path) -> None:
    _write(repo, ".gitignore", "out/\nlocal.md\n")
    _write(repo, "doc.md", "a gate\n")
    _write(repo, "out/doc.md", "a gate\n")
    _write(repo, "local.md", "a gate\n")
    _write(repo, "src/_generated/stub.rs", "// a gate\n")
    _write(repo, "src/lib.rs", "// fine\n")
    _write(repo, "logo.png", "gate")
    scanned = prosecheck.scan(repo, [repo], PATTERN, range(5, 9))
    assert scanned.files == 4
    assert scanned.problems == [Problem(Path("doc.md"), 1, prosecheck.BANNED, 'banned word "gate"')]


def test_scan_reads_a_named_file_even_when_git_ignores_it(repo: Path) -> None:
    _write(repo, ".gitignore", "local.md\n")
    _write(repo, "local.md", "a gate\n")
    scanned = prosecheck.scan(repo, [repo / "local.md"], PATTERN, range(0))
    assert (scanned.files, len(scanned.problems)) == (1, 1)


def test_scan_walks_a_named_directory(repo: Path) -> None:
    _write(repo, "docs/a.md", "a gate\n")
    _write(repo, "docs/deep/b.md", "a gate\n")
    _write(repo, "other.md", "a gate\n")
    scanned = prosecheck.scan(repo, [repo / "docs"], PATTERN, range(0))
    assert [problem.path for problem in scanned.problems] == [
        Path("docs/a.md"),
        Path("docs/deep/b.md"),
    ]


def test_a_path_outside_the_root_is_an_error(
    repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    with pytest.raises(prosecheck.UnreadableFileError, match="is not inside"):
        prosecheck.scan(repo, [outside], PATTERN, range(0))


def test_a_file_that_is_not_text_is_an_error(repo: Path) -> None:
    (repo / "bad.md").write_bytes(b"\xff\xfe")
    with pytest.raises(prosecheck.UnreadableFileError, match="cannot read"):
        prosecheck.scan(repo, [repo], PATTERN, range(0))


def test_python_that_cannot_be_parsed_is_an_error(repo: Path) -> None:
    _write(repo, "bad.py", "def f(:\n")
    with pytest.raises(prosecheck.UnreadableFileError, match=r"cannot parse bad\.py"):
        prosecheck.scan(repo, [repo], PATTERN, range(0))


def test_main_passes_a_clean_tree_and_exempts_the_table(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "a.py", '"""Plain."""\n')
    assert prosecheck.main(["--root", str(repo)]) == 0
    assert capsys.readouterr().out == (
        "prosecheck OK: 2 file(s) read, with no banned word and no docstring "
        "or comment block over 3 lines\n"
    )


def test_main_reports_every_problem(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "a.py", "# gate\n" + LONG_DOCSTRING + LONG_BLOCK)
    assert prosecheck.main(["--root", str(repo), str(repo / "a.py")]) == 1
    captured = capsys.readouterr()
    assert captured.out == (
        'a.py:1: banned word "gate"\n'
        "a.py:2: docstring has 4 lines, at most 3\n"
        "a.py:8: comment block has 4 lines, at most 3\n"
    )
    assert captured.err == (
        "\nprosecheck: 1 banned word(s), 1 long docstring(s) "
        "and 1 long comment block(s) in 1 file(s) read\n"
    )


def test_main_defaults_to_the_current_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, "doc.md", "a gate\n")
    monkeypatch.chdir(repo)
    assert prosecheck.main([]) == 1


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert prosecheck.main(["--root", str(tmp_path / "missing")]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_fails_without_the_table(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(repo, "AGENTS.md", "# Rules\n")
    assert prosecheck.main(["--root", str(repo)]) == 2
    assert "has no table whose first column is headed" in capsys.readouterr().err


def test_main_fails_outside_a_git_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "AGENTS.md", RULES)
    assert prosecheck.main(["--root", str(tmp_path)]) == 2
    assert "git cannot say what" in capsys.readouterr().err


def test_main_fails_when_no_checked_file_was_read(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "logo.png", "x")
    assert prosecheck.main(["--root", str(repo), str(repo / "logo.png")]) == 2
    assert capsys.readouterr().err == (
        "prosecheck: no file of a checked type was read, so nothing was checked\n"
    )


def test_an_exempt_module_docstring_is_not_checked(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, "a.py", BANNED_DOCSTRING + LONG_BLOCK)
    monkeypatch.setattr(prosecheck, "EXEMPTIONS", (Exemption("a.py", None, "it is read"),))
    scanned = prosecheck.scan(repo, [repo / "a.py"], PATTERN, range(0))
    assert [problem.message for problem in scanned.problems] == [
        "comment block has 4 lines, at most 3"
    ]


def test_exempt_decorated_docstrings_are_not_checked(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(repo, "a.py", LONG_DOCSTRING + DECORATED_TOOL)
    monkeypatch.setattr(prosecheck, "EXEMPTIONS", (Exemption("a.py", "server.tool", "model"),))
    scanned = prosecheck.scan(repo, [repo / "a.py"], PATTERN, range(0))
    assert [problem.line for problem in scanned.problems] == [1]


def test_an_exemption_for_a_file_that_is_gone_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(prosecheck, "EXEMPTIONS", (Exemption("gone.py", None, "it is read"),))
    assert prosecheck.main(["--root", str(repo)]) == 2
    assert "the exemption for gone.py names a file that is not there" in capsys.readouterr().err


def test_an_exemption_for_a_module_docstring_that_is_gone_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "a.py", "x = 1\n")
    monkeypatch.setattr(prosecheck, "EXEMPTIONS", (Exemption("a.py", None, "it is read"),))
    assert prosecheck.main(["--root", str(repo)]) == 2
    assert "names the module docstring, which is not there" in capsys.readouterr().err


def test_an_exemption_for_a_decorator_that_is_gone_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "a.py", '"""Plain."""\n')
    monkeypatch.setattr(prosecheck, "EXEMPTIONS", (Exemption("a.py", "server.tool", "model"),))
    assert prosecheck.main(["--root", str(repo)]) == 2
    assert "names docstrings under @server.tool, which is not there" in capsys.readouterr().err


def test_this_repositorys_exemptions_all_name_prose_that_is_there() -> None:
    covered = prosecheck.exempt_lines(REPO_ROOT, EXEMPTIONS)
    assert sorted(covered) == sorted(Path(item.path) for item in EXEMPTIONS)
    assert all(lines for lines in covered.values())
