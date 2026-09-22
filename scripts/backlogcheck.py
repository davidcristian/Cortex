"""Check each backlog index against the task files it describes, or regenerate it."""

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import backloganchors
import backlogindex
import bannedwords
from backlog import Task, TaskFileError, load
from backloganchors import local_links

BACKLOGS = (
    ("refinements", Path("docs/refinements"), "area"),
    ("host", Path("docs/host"), "session"),
)
RULES_NAME = "AGENTS.md"


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


def other_texts(root: Path) -> list[tuple[Path, str]]:
    """Return every markdown file outside the task directories and indexes, with its text."""
    bases = [(root / base).resolve() for _, base, _ in BACKLOGS]
    indexes = {base / "index.md" for base in bases}
    directories = {base / "tasks" for base in bases}
    sources: list[tuple[Path, str]] = []
    for path in backloganchors.markdown_files(root):
        resolved = path.resolve()
        if resolved in indexes or resolved.parent in directories:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # backloganchors.check reports a file it cannot read.
            continue
        sources.append((path, text))
    return sources


def check_stray(directory: Path) -> list[str]:
    """Return one problem per entry in ``directory`` that is not a task file."""
    return [
        f"{path}: a tasks directory contains task files and nothing else"
        for path in sorted(directory.iterdir())
        if path.is_dir() or path.suffix != ".md"
    ]


def slug_pattern(root: Path) -> re.Pattern[str]:
    """Return the banned words of ``root``'s AGENTS.md as one pattern, hyphens read as spaces."""
    table = bannedwords.read_table(root / RULES_NAME)
    return bannedwords.compile_words(word.replace("-", " ") for word in table.words)


def check_slugs(root: Path, directory: Path, pattern: re.Pattern[str]) -> list[str]:
    """Return one problem per banned word in the slug of a task file in ``directory``."""
    return [
        f"{path.relative_to(root)}: the file name uses the banned word "
        f"{found.group().lower()!r}; rename it from its title"
        for path in sorted(directory.glob("*.md"))
        for found in pattern.finditer(path.stem.partition("-")[2].replace("-", " "))
    ]


def run_one(
    root: Path, kind: str, base: Path, group_word: str, *, write: bool
) -> tuple[list[str], frozenset[str] | None]:
    """Check one backlog, or regenerate it; return its problems and the anchors in its index."""
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
    # The links are checked on the regenerated text, because a write run replaces the file.
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
    """Run the check; print any problems and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Check each backlog index against the task files it describes.",
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
        name = f"{base}/index.md"
        indexes[(root / name).resolve()] = backloganchors.Index(name=name, anchors=offered)
    problems.extend(check_links(root, other_texts(root)))
    try:
        pattern = slug_pattern(root)
    except bannedwords.TableError as err:
        problems.append(f"the task file names cannot be checked: {err}")
    else:
        for _, base, _ in BACKLOGS:
            problems.extend(check_slugs(root, root / base / "tasks", pattern))
    problems.extend(backloganchors.check(root, indexes))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\nbacklogcheck: {len(problems)} problem(s). A task's status is written on its own "
            f"Status line and nowhere else; the index is generated from those files by "
            f"`just backlog`. A relative link anywhere in the repo must resolve, and its "
            f"fragment must name a heading the document it aims at really offers.",
            file=sys.stderr,
        )
        return 1
    print(
        "backlogcheck OK: every index matches its task files, every link resolves, and no task "
        "file name uses a banned word"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
