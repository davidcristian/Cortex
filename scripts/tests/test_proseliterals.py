from pathlib import Path

import pytest

import bannedwords
import proseliterals
from commentblocks import SourceError
from proseliterals import ExemptionError, Literal, LiteralExemption
from slashcomments import RUST, TYPESCRIPT, Syntax

REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERN = bannedwords.compile_words(["gate", "gates"])


def _texts(source: str) -> list[str]:
    return [found.text for found in proseliterals.prose_literals(source)]


def _hits(source: str) -> list[str]:
    runs = proseliterals.literal_runs(proseliterals.prose_literals(source), ())
    return [hit.word for run in runs for hit in bannedwords.find_words(run, PATTERN)]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_literal_holding_two_words_is_prose() -> None:
    assert proseliterals.prose_literals('x = "a gate here"\n') == [
        Literal(line=1, text="a gate here", name="x")
    ]


@pytest.mark.parametrize(
    "source",
    [
        'x = "gate"\n',
        'x = "gate-name"\n',
        'x = b"a gate here"\n',
        "x = 3\n",
        "",
        'x = {"a gate here": 1}\n',
        'y = d["a gate here"]\n',
    ],
)
def test_a_word_a_key_a_subscript_or_no_string_is_not_prose(source: str) -> None:
    assert _texts(source) == []


def test_docstrings_are_left_to_the_docstring_reader() -> None:
    source = (
        '"""A gate here."""\n\n\nclass A:\n    """A gate here."""\n\n'
        '    def f(self) -> None:\n        """A gate here."""\n\n'
        '    async def g(self) -> None:\n        """A gate here."""\n'
    )
    assert _texts(source) == []


def test_a_dict_value_and_a_bare_string_after_code_are_read() -> None:
    source = 'x = 1\n"""A gate here."""\ny = {"k": "the gates close"}\n'
    assert _texts(source) == ["A gate here.", "the gates close"]


def test_an_f_string_is_read_whole_with_a_placeholder_for_each_value() -> None:
    assert _texts('x = f"{n} gates"\n') == ["{} gates"]
    assert _texts('x = f"{n:>{w}} gates"\n') == ["{} gates"]
    assert _texts('x = f"{n} of the gates close"\n') == ["{} of the gates close"]


def test_paths_flags_and_code_spans_are_masked() -> None:
    source = 'x = "see scripts/gate.py, gate.md: and --gate or -g and `gate` now"\n'
    assert _hits(source) == []
    assert _hits('x = "the gate is shut"\n') == ["gate"]


def test_a_literal_over_several_lines_is_read_as_one_line() -> None:
    assert proseliterals.prose_literals('x = 1\ny = """a\ngate here"""\n') == [
        Literal(line=2, text="a gate here", name="y")
    ]


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ('a = b = "a gate here"\n', "a"),
        ('x: str = "a gate here"\n', None),
        ('obj.x = "a gate here"\n', None),
        ('def f() -> None:\n    x = "a gate here"\n', None),
    ],
)
def test_a_literal_is_named_by_its_module_level_assignment(source: str, name: str | None) -> None:
    assert [found.name for found in proseliterals.prose_literals(source)] == [name]


def test_literals_are_returned_in_line_order() -> None:
    source = 'x = f(\n    g("one two"),\n    "three four",\n)\ny = "five six"\n'
    assert [found.line for found in proseliterals.prose_literals(source)] == [2, 3, 5]


def test_source_that_cannot_be_parsed_is_an_error() -> None:
    with pytest.raises(SourceError):
        proseliterals.prose_literals("x = (\n")


@pytest.mark.parametrize(
    "path",
    [
        "scripts/a.py",
        "brain/packages/core/src/cortex_core/a.py",
        "brain/packages/core/src/cortex_core/sub/a.py",
        "body/crates/core/src/a.rs",
        "body/app/src-tauri/src/a.rs",
        "body/app/src/bridge/a.ts",
        "body/app/src/components/A.tsx",
        "justfile",
        "docker/postgres/backup.sh",
        "scripts/a.sh",
    ],
)
def test_scripts_the_brain_and_the_body_sources_are_read(path: str) -> None:
    assert proseliterals.reads_literals(Path(path))


@pytest.mark.parametrize(
    "path",
    [
        "scripts/tests/test_a.py",
        "scripts/a.md",
        "brain/packages/core/tests/test_a.py",
        "brain/packages/core/a.py",
        "body/crates/a.py",
        "body/crates/core/tests/a.rs",
        "body/app/src/bridge/a.test.ts",
        "body/app/src/components/A.test.tsx",
        "body/app/src/a.css",
        "a.py",
        "a.rs",
        "justfile.md",
    ],
)
def test_tests_and_other_trees_are_not_read(path: str) -> None:
    assert not proseliterals.reads_literals(Path(path))


def _slash_hits(source: str, syntax: Syntax = RUST) -> list[str]:
    runs = proseliterals.literal_runs(proseliterals.slash_literals(source, syntax), ())
    return [hit.word for run in runs for hit in bannedwords.find_words(run, PATTERN)]


def test_a_rust_or_typescript_literal_holding_two_words_is_prose() -> None:
    source = 'let a = "gate";\nlet b = f("the gate is shut");\n'
    assert proseliterals.slash_literals(source, RUST) == [
        Literal(line=2, text="the gate is shut", name=None)
    ]
    assert _slash_hits("const s = `${n} gates`;\n", TYPESCRIPT) == ["gates"]


@pytest.mark.parametrize(
    ("source", "hits"),
    [
        ('x("one\\ngate here")', ["gate"]),
        ('x("one\\tgate here")', ["gate"]),
        ('x("the \\"gate\\" is shut")', ["gate"]),
        ('x("ab\\cgate here")', []),
        ('x("see scripts/gate.rs and `gate` now")', []),
    ],
)
def test_escapes_are_read_as_the_text_they_stand_for(source: str, hits: list[str]) -> None:
    assert _slash_hits(source) == hits


@pytest.mark.parametrize(
    ("name", "source"),
    [
        ("a.rs", 'let x = "a gate here";\n'),
        ("a.ts", "const x = 'a gate here';\n"),
        ("a.tsx", "const x = <p title={`a gate ${n}`} />;\n"),
        ("a.py", 'x = "a gate here"\n'),
        ("justfile", 'r:\n    echo "a gate {{ gate }} here"\n'),
        ("docker/a.sh", "echo 'a gate' \"{{gate}} is shut\" >&2\n"),
    ],
)
def test_file_literals_read_each_language_with_its_own_reader(name: str, source: str) -> None:
    literals = proseliterals.file_literals(Path(name), source)
    runs = proseliterals.literal_runs(literals, ())
    assert [hit.word for run in runs for hit in bannedwords.find_words(run, PATTERN)] == ["gate"]


@pytest.mark.parametrize(
    ("source", "hits"),
    [
        ('echo "a gate here" >&2', ["gate"]),
        ('echo "one\\ngate here"', ["gate"]),
        ('echo "the $gate here"', []),
        ('echo "the ${gate} here"', []),
        ('echo "run --gate now"', []),
        ("echo 'a gate here'", []),
    ],
)
def test_a_shell_string_is_read_with_its_expansions_and_flags_masked(
    source: str, hits: list[str]
) -> None:
    runs = proseliterals.literal_runs(proseliterals.shell_literals(source, just=False), ())
    assert [hit.word for run in runs for hit in bannedwords.find_words(run, PATTERN)] == hits


def test_literal_runs_leave_out_exempt_names() -> None:
    literals = proseliterals.prose_literals('x = "a gate here"\ny = "the gate"\nf("a gate")\n')
    assert proseliterals.literal_runs(literals, {"x"}) == [[(2, "the gate")], [(3, "a gate")]]


def test_exempt_names_are_merged_per_file(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 'X = "a gate here"\nY = f"{n} gates"\n')
    exemptions = (
        LiteralExemption("a.py", ("X",), "model"),
        LiteralExemption("a.py", ("Y",), "model"),
    )
    covered = proseliterals.exempt_names(tmp_path, exemptions, PATTERN, _read)
    assert covered == {Path("a.py"): frozenset({"X", "Y"})}


def test_an_exemption_for_a_file_that_is_gone_fails(tmp_path: Path) -> None:
    exemptions = (LiteralExemption("gone.py", ("X",), "model"),)
    with pytest.raises(ExemptionError, match=r"gone\.py names a file that is not there"):
        proseliterals.exempt_names(tmp_path, exemptions, PATTERN, _read)


@pytest.mark.parametrize("source", ['X = "a plain sentence"\n', 'Z = "a gate here"\n'])
def test_an_exemption_whose_name_holds_no_banned_word_fails(tmp_path: Path, source: str) -> None:
    _write(tmp_path, "a.py", source)
    exemptions = (LiteralExemption("a.py", ("X",), "model"),)
    with pytest.raises(ExemptionError, match="names X, and no string assigned to it holds"):
        proseliterals.exempt_names(tmp_path, exemptions, PATTERN, _read)


def test_this_repositorys_literal_exemptions_all_name_a_banned_word() -> None:
    table = bannedwords.read_table(REPO_ROOT / "AGENTS.md")
    pattern = bannedwords.compile_words(table.words)
    exemptions = proseliterals.EXEMPTIONS
    covered = proseliterals.exempt_names(REPO_ROOT, exemptions, pattern, _read)
    assert sorted(covered) == sorted(Path(item.path) for item in exemptions)
