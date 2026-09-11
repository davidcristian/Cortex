"""Repo gate: hold each backlog index to the task files it claims to describe."""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

import backloganchors
import backlogindex
from backlog import Task, TaskFileError, load
from backloganchors import local_links

BACKLOGS = (
    ("refinements", Path("docs/refinements"), "area"),
    ("host", Path("docs/host"), "sitting"),
)


def check_links(root: Path, sources: Iterable[tuple[Path, str]]) -> list[str]:
    """Return one problem per relative link in ``sources`` that does not resolve to a file."""
    return [
        f"{path.relative_to(root)}: link {target!r} does not resolve"
        for path, text in sources
        for target in local_links(text)
        if not (path.parent / target).resolve().exists()
    ]


def task_texts(tasks: list[Task]) -> list[tuple[Path, str]]:
    """Return each task file with its text, the sources the link check reads off disk."""
    return [(task.path, task.path.read_text(encoding="utf-8")) for task in tasks]


def check_stray(directory: Path) -> list[str]:
    """Return one problem per entry in ``directory`` that is not a task file."""
    return [
        f"{path}: a tasks directory holds task files and nothing else"
        for path in sorted(directory.iterdir())
        if path.is_dir() or path.suffix != ".md"
    ]


def run_one(
    root: Path, kind: str, base: Path, group_word: str, *, write: bool
) -> tuple[list[str], frozenset[str] | None]:
    """Check (or regenerate) one backlog; return its problems and the anchors its index offers."""
    directory = root / base / "tasks"
    index = root / base / "index.md"
    if not directory.is_dir():
        return [f"{base}/tasks is missing; the backlog is one file per task"], None
    if not index.is_file():
        return [f"{base}/index.md is missing"], None
    problems = check_stray(directory)
    try:
        tasks = load(directory, kind)
    except TaskFileError as err:
        return [*problems, str(err)], None
    problems.extend(check_links(root, task_texts(tasks)))
    block = backlogindex.render(tasks, group_word)
    existing = index.read_text(encoding="utf-8")
    try:
        wanted = backlogindex.splice(existing, block)
    except ValueError as err:
        return [*problems, f"{base}/index.md: {err}"], None
    # The index's links are judged after the splice and on its result, never on the file: a
    # write run replaces that file, so a link only the stale file carries would fail the run
    # that removes it, and one only the fresh block carries would pass the run that writes it.
    problems.extend(check_links(root, [(index, wanted)]))
    if wanted != existing:
        if write:
            index.write_text(wanted, encoding="utf-8")
            print(f"backlogcheck: rewrote {base}/index.md")
        else:
            problems.append(
                f"{base}/index.md is out of date with its {len(tasks)} task files; "
                f"run `just backlog`"
            )
    opens = sum(1 for task in tasks if task.status.is_open)
    print(f"backlogcheck: {base} has {len(tasks)} tasks, {opens} open")
    return problems, backloganchors.anchors(wanted)


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any problems and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Hold each backlog index to the task files it describes.",
    )
    parser.add_argument(
        "--root", type=Path, default=Path(), help="repo root (default: current directory)"
    )
    parser.add_argument(
        "--write", action="store_true", help="regenerate each index instead of checking it"
    )
    args = parser.parse_args(argv)
    root: Path = args.root
    if not root.is_dir():
        print(f"backlogcheck: root {root} is not a directory", file=sys.stderr)
        return 2
    problems: list[str] = []
    indexes: dict[Path, backloganchors.Index] = {}
    for kind, base, group_word in BACKLOGS:
        found, offered = run_one(root, kind, base, group_word, write=args.write)
        problems.extend(found)
        # Registered even when its rendering is unknown, so the anchor scan treats this
        # document as an index and leaves it alone rather than reading the stale file.
        name = f"{base}/index.md"
        indexes[(root / name).resolve()] = backloganchors.Index(name=name, anchors=offered)
    problems.extend(backloganchors.check(root, indexes))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\nbacklogcheck: {len(problems)} problem(s). A task's status is written on its own "
            f"Status line and nowhere else; the index is generated from those files by "
            f"`just backlog`, and a fragment anywhere in the repo must name a heading the "
            f"document it aims at really offers.",
            file=sys.stderr,
        )
        return 1
    print("backlogcheck OK: every backlog index matches its task files, and every fragment lands")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
