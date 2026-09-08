"""Tests for what a module under `scripts/` calls, read out of its syntax.

Each case here is a source fragment rather than a file, because what is under test is the shape a
call is written in and nothing else. The two obligations this reader serves are held over the real
tree by the suites beside `gitenv.py` and `treewalk.py`; these are the shapes those two must
recognize, including the ones that were written here and never recognized before.
"""

import ast

import gatecalls


def _reads(source: str) -> list[tuple[int, str]]:
    """Every tree read one fragment makes, as a line and the function it names."""
    return [(read.line, read.called) for read in gatecalls.tree_reads(ast.parse(source))]


def _calls(source: str) -> list[tuple[int, str | None]]:
    """Every git call one fragment makes, as a line and the environment it hands."""
    return [(call.line, call.environment) for call in gatecalls.git_calls(ast.parse(source))]


def test_the_two_calls_that_always_descend_are_read_as_tree_reads() -> None:
    """`walk` and `rglob` descend whatever they are called on, so neither needs a pattern."""
    assert _reads("root.walk()\nroot.rglob('*.py')\n") == [(1, "walk"), (2, "rglob")]


def test_a_walk_over_a_syntax_tree_is_not_a_tree_read() -> None:
    """`ast.walk` is told from a directory walk by the module it is spelled on."""
    assert _reads("ast.walk(tree)\n") == []
    assert _reads("thing.ast.walk(tree)\n") == [(1, "walk")]
    assert _reads("walk(tree)\n") == [(1, "walk")]


def test_a_glob_is_read_by_its_pattern() -> None:
    """A pattern naming one directory's entries is a listing; `**` reaches below it."""
    assert _reads("root.glob('*.py')\n") == []
    assert _reads("root.glob('**/*.py')\niglob('**/*.md')\n") == [(1, "glob"), (2, "iglob")]


def test_a_glob_whose_pattern_cannot_be_read_is_a_tree_read() -> None:
    """A pattern this reader cannot see is answered as a descent rather than passed over.

    The alternative is the failure this whole reader exists to remove: a call nobody can judge,
    reported as one nobody has to.
    """
    assert _reads("root.glob(pattern)\nroot.glob()\nroot.glob(7)\n") == [
        (1, "glob"),
        (2, "glob"),
        (3, "glob"),
    ]


def test_a_call_on_a_call_names_no_function_this_reader_knows() -> None:
    """A callee that is neither a name nor an attribute is not one of the calls looked for."""
    assert _reads("factory()()\n") == []


def test_an_argv_written_inside_the_call_is_a_git_call() -> None:
    """The shape three gates here write, and the one the old text search recognized."""
    assert _calls("run(['git', '-C', root], env=git_env())\n") == [(1, "git_env")]


def test_an_argv_assigned_above_the_call_is_a_git_call() -> None:
    """The near miss the text search shared with the formatter, in both assignment forms."""
    assert _calls("argv = ['git', 'status']\nrun(argv, env=git_env())\n") == [(2, "git_env")]
    annotated = "argv: list[str] = ('git', 'status')\nrun(argv, env=gitenv.git_env())\n"
    assert _calls(annotated) == [(2, "git_env")]


def test_a_name_this_reader_cannot_tie_to_an_argv_is_not_a_git_call() -> None:
    """A declaration with no value, an assignment to something other than a name, and a name
    assigned another name: none of the three ties a name to an argv, so no call is reported."""
    assert _calls("argv: list[str]\nrun(argv)\n") == []
    assert _calls("holder.argv = ['git', 'status']\nrun(holder.argv)\n") == []
    assert _calls("argv = ['git']\nsecond = argv\nrun(second)\n") == []


def test_what_is_not_a_git_argv_is_not_a_git_call() -> None:
    """A call handed nothing, another program's argv, an empty list, or a number first."""
    assert _calls("run()\nrun(['docker', 'pull'])\nrun([])\nrun([7, 'git'])\n") == []


def test_the_environment_is_the_function_the_keyword_calls() -> None:
    """A call with no environment, one handed a value rather than a call, and one handed both."""
    assert _calls("run(['git'], check=False)\n") == [(1, None)]
    assert _calls("run(['git'], env=environment)\n") == [(1, None)]
    assert _calls("run(['git'], check=False, env=os.environ.copy())\n") == [(1, "copy")]


def test_calls_come_back_in_line_order() -> None:
    """Both readers answer in the order a reader of the file meets the calls."""
    source = "run(['git', 'a'], env=git_env())\nroot.walk()\nrun(['git', 'b'])\n"
    assert _calls(source) == [(1, "git_env"), (3, None)]
    assert _reads(source) == [(2, "walk")]
