"""Repo gate: hold each backlog index to the task files it claims to describe."""

import argparse
import sys
from pathlib import Path

import backlogindex
from backlog import Task, TaskFileError, load, local_links

BACKLOGS = (
    ("refinements", Path("docs/refinements"), "area"),
    ("host", Path("docs/host"), "sitting"),
)


def check_links(root: Path, tasks: list[Task], extra: Path) -> list[str]:
    """Return one problem per relative link that does not resolve to a file on disk."""
    problems: list[str] = []
    sources = [task.path for task in tasks]
    if extra.is_file():
        sources.append(extra)
    for path in sources:
        text = path.read_text(encoding="utf-8")
        problems.extend(
            f"{path.relative_to(root)}: link {target!r} does not resolve"
            for target in local_links(text)
            if not (path.parent / target).resolve().exists()
        )
    return problems


def check_stray(directory: Path) -> list[str]:
    """Return one problem per entry in ``directory`` that is not a task file."""
    return [
        f"{path}: a tasks directory holds task files and nothing else"
        for path in sorted(directory.iterdir())
        if path.is_dir() or path.suffix != ".md"
    ]


def run_one(root: Path, kind: str, base: Path, group_word: str, *, write: bool) -> list[str]:
    """Check (or regenerate) one backlog; return its problems, empty when it is clean."""
    directory = root / base / "tasks"
    index = root / base / "index.md"
    if not directory.is_dir():
        return [f"{base}/tasks is missing; the backlog is one file per task"]
    if not index.is_file():
        return [f"{base}/index.md is missing"]
    problems = check_stray(directory)
    try:
        tasks = load(directory, kind)
    except TaskFileError as err:
        return [*problems, str(err)]
    problems.extend(check_links(root, tasks, index))
    block = backlogindex.render(tasks, group_word)
    existing = index.read_text(encoding="utf-8")
    try:
        wanted = backlogindex.splice(existing, block)
    except ValueError as err:
        return [*problems, f"{base}/index.md: {err}"]
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
    return problems


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
    for kind, base, group_word in BACKLOGS:
        problems.extend(run_one(root, kind, base, group_word, write=args.write))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\nbacklogcheck: {len(problems)} problem(s). A task's status is written on its own "
            f"Status line and nowhere else; the index is generated from those files by "
            f"`just backlog`.",
            file=sys.stderr,
        )
        return 1
    print("backlogcheck OK: every backlog index matches its task files")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
