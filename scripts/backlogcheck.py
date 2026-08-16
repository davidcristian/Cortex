"""Repo gate: hold each backlog index to the task files it claims to describe.

Run without arguments it checks; with `--write` it regenerates. That split is the whole
mechanism, and it is `cargo fmt --check` applied to a backlog: the index cannot be edited
into disagreement with the tasks, because the only way to change it is to change a task
file and regenerate, and the gate fails on any difference. What the predecessor layout
asked a person to keep true by hand, this asks a machine to keep true by construction.

Five things fail here:

1. A task file outside the layout: a name that is not `NNN-slug.md`, a missing or
   duplicated field, a status outside the grammar, a title restating its own status, a
   number already used, or one of the two waiting states not naming its trigger.
2. A relative link that does not resolve. Task files are moved and renumbered as the
   backlog is worked, and a link is the one part of a move that fails silently.
3. A fragment aimed at a heading a backlog index does not render, which is the other half
   of that same link and the half a rename breaks while the path keeps resolving.
   `backloganchors.py` holds it, over every markdown file under the root rather than over
   the backlog alone, because most pointers at these anchors live in decision records.
4. An index whose generated block is stale, missing, or hand-edited.
5. A `tasks/` directory holding something that is not a task file.
"""

import argparse
import sys
from pathlib import Path

import backloganchors
import backlogindex
from backlog import Task, TaskFileError, load
from backloganchors import local_links

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


def run_one(
    root: Path, kind: str, base: Path, group_word: str, *, write: bool
) -> tuple[list[str], frozenset[str] | None]:
    """Check (or regenerate) one backlog; return its problems and the anchors its index offers.

    The anchors are None exactly when this backlog is broken enough that what its index
    would render is unknown, in which case the pointers aimed at it go unjudged this run
    and the run is already failing on the reason.
    """
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
    problems.extend(check_links(root, tasks, index))
    block = backlogindex.render(tasks, group_word)
    existing = index.read_text(encoding="utf-8")
    try:
        wanted = backlogindex.splice(existing, block)
    except ValueError as err:
        return [*problems, f"{base}/index.md: {err}"], None
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
        if offered is not None:
            name = f"{base}/index.md"
            indexes[(root / name).resolve()] = backloganchors.Index(name=name, anchors=offered)
    problems.extend(backloganchors.check(root, indexes))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\nbacklogcheck: {len(problems)} problem(s). A task's status is written on its own "
            f"Status line and nowhere else; the index is generated from those files by "
            f"`just backlog`, and a pointer into one must name a heading it renders.",
            file=sys.stderr,
        )
        return 1
    print("backlogcheck OK: every backlog index matches its task files and the pointers into it")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
