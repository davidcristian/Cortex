import ast

import gatecalls


def _reads(source: str) -> list[tuple[int, str]]:
    """Return every tree read in ``source``, as a line number and the function called."""
    return [(read.line, read.called) for read in gatecalls.tree_reads(ast.parse(source))]


def _calls(source: str) -> list[tuple[int, str | None]]:
    """Return every git call in ``source``, as a line number and the environment passed."""
    return [(call.line, call.environment) for call in gatecalls.git_calls(ast.parse(source))]


def test_the_two_calls_that_always_descend_are_read_as_tree_reads() -> None:
    assert _reads("root.walk()\nroot.rglob('*.py')\n") == [(1, "walk"), (2, "rglob")]


def test_a_walk_over_a_syntax_tree_is_not_a_tree_read() -> None:
    assert _reads("ast.walk(tree)\n") == []
    assert _reads("thing.ast.walk(tree)\n") == [(1, "walk")]
    assert _reads("walk(tree)\n") == [(1, "walk")]


def test_a_glob_is_read_by_its_pattern() -> None:
    assert _reads("root.glob('*.py')\n") == []
    assert _reads("root.glob('**/*.py')\niglob('**/*.md')\n") == [(1, "glob"), (2, "iglob")]


def test_a_glob_whose_pattern_cannot_be_read_is_a_tree_read() -> None:
    assert _reads("root.glob(pattern)\nroot.glob()\nroot.glob(7)\n") == [
        (1, "glob"),
        (2, "glob"),
        (3, "glob"),
    ]


def test_a_call_on_a_call_names_no_function_this_reader_knows() -> None:
    assert _reads("factory()()\n") == []


def test_an_argv_written_inside_the_call_is_a_git_call() -> None:
    assert _calls("run(['git', '-C', root], env=git_env())\n") == [(1, "git_env")]


def test_an_argv_assigned_above_the_call_is_a_git_call() -> None:
    assert _calls("argv = ['git', 'status']\nrun(argv, env=git_env())\n") == [(2, "git_env")]
    annotated = "argv: list[str] = ('git', 'status')\nrun(argv, env=gitenv.git_env())\n"
    assert _calls(annotated) == [(2, "git_env")]


def test_a_name_this_reader_cannot_tie_to_an_argv_is_not_a_git_call() -> None:
    assert _calls("argv: list[str]\nrun(argv)\n") == []
    assert _calls("holder.argv = ['git', 'status']\nrun(holder.argv)\n") == []
    assert _calls("argv = ['git']\nsecond = argv\nrun(second)\n") == []


def test_what_is_not_a_git_argv_is_not_a_git_call() -> None:
    assert _calls("run()\nrun(['docker', 'pull'])\nrun([])\nrun([7, 'git'])\n") == []


def test_the_environment_is_the_function_the_keyword_calls() -> None:
    assert _calls("run(['git'], check=False)\n") == [(1, None)]
    assert _calls("run(['git'], env=environment)\n") == [(1, None)]
    assert _calls("run(['git'], check=False, env=os.environ.copy())\n") == [(1, "copy")]


def test_calls_come_back_in_line_order() -> None:
    source = "run(['git', 'a'], env=git_env())\nroot.walk()\nrun(['git', 'b'])\n"
    assert _calls(source) == [(1, "git_env"), (3, None)]
    assert _reads(source) == [(2, "walk")]
