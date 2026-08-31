"""Read and validate the per-task backlog files under `docs/refinements` and `docs/host`.

One task is one file, and its **Status:** line is the only place its state is written down. The
layout before this one kept the same status in three places, the entry itself, its area header and
a cell in the index table, and the three drifted apart while agreeing with each other: a header and
a cell both named the wrong set and matched, so nothing compared them to the entries. The index is
rendered from these files by `backlogindex.py`, and `backlogcheck.py` fails when the rendered form
and the committed one disagree (ADR-0039).

The two backlogs hold different kinds of not-done and so carry different fields, which is why
`Kind` exists rather than one union of optional fields:

- **refinements** is deferred design: work anyone can pick up once a seam, a consumer, or a
  decision unblocks it. It carries an `Area` and, when its state is one defined by a named trigger,
  a `Trigger`.
- **host** is built code waiting on hardware this repo is not developed on. It carries the
  `Sitting` one bring-up covers and the `Capability` that bring-up needs.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FILENAME = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
FIELD = re.compile(r"^\*\*([A-Za-z]+):\*\* +(.+?) *$")
# A title names the work, never its state. "closed" and "done" are left out of this list on
# purpose: both are ordinary adjectives in these titles (a closed section, a closed list), so
# banning them would reject honest names. A year is banned outright, a date in a title being a
# status restatement every time.
TITLE_BANS = ("landed", "declined", "satisfied")
TITLE_YEAR = re.compile(r"\b(19|20)\d{2}\b")

# The open states, each mapped to the heading it is filed under. A state says what unblocks the
# task, so a reader picks a bucket rather than a priority number.
OPEN_STATES = {
    "actionable": "Actionable now",
    "a seam or port change comes first": "Actionable, once a seam or port changes",
    "fix when it bites": "Fix when it bites",
    "dead until a consumer": "Dead until a consumer exists",
    "feature breadth": "Feature breadth, on request",
    "blocked on host hardware": "Blocked on hardware this repo is not developed on",
}
# Two states are defined by waiting for something nobody is doing yet, so each must name the
# thing that would reopen it. Without that, a deferral cannot be told from a task that was dropped.
NEEDS_TRIGGER = frozenset({"fix when it bites", "dead until a consumer"})
# The one legal way to satisfy that requirement without inventing a trigger. Twelve tasks arrived
# from the per-area layout in a waiting state with nothing recorded about what would fire them,
# which is the gap this rule exposes, so writing the gap down is preferred to guessing a trigger or
# dropping the rule. The index counts these, so the number can be driven to zero by reading them.
UNRECORDED = "unrecorded"
CLOSED_VERBS = ("landed", "declined", "satisfied")

HOST_STATES = ("never attempted", "attempted", "done")
# A standing item is neither open nor closed: an observation made over months of real use, or an
# obligation on every change rather than once. Counting it as open overstates what remains and
# counting it as closed claims it finished, so it is counted on its own. Host only, since a
# refinement is deferred work and work that never closes is not deferred.
STANDING = "standing"

KIND_FIELDS = {
    "refinements": (("Status", "Area", "Origin"), ("Trigger",)),
    "host": (("Status", "Sitting", "Capability", "Origin"), ()),
}
CAPABILITIES = ("W", "G", "W+G")


class TaskFileError(Exception):
    """A task file does not satisfy the layout every reader and the index rely on."""


@dataclass(frozen=True)
class Status:
    """A parsed **Status:** line: what state the task is in and since when."""

    state: str
    on: date | None
    detail: str

    @property
    def is_open(self) -> bool:
        """Return True when the task is still work somebody could pick up."""
        return self.state in OPEN_STATES or self.state in ("never attempted", "attempted")

    @property
    def is_standing(self) -> bool:
        """Return True when the task never closes, so no count may call it open or closed."""
        return self.state == STANDING

    @property
    def bucket(self) -> str:
        """Return the index heading this status files under."""
        if self.state in OPEN_STATES:
            return OPEN_STATES[self.state]
        if self.state == "never attempted":
            return "Never attempted"
        if self.state == "attempted":
            return "Attempted, inconclusive"
        if self.state == STANDING:
            return "Standing, never closes"
        return self.state.capitalize()


@dataclass(frozen=True)
class Task:
    """One backlog task: its file, its identity, and the fields the index renders."""

    kind: str
    number: int
    slug: str
    path: Path
    title: str
    status: Status
    fields: dict[str, str]

    @property
    def ident(self) -> str:
        """Return the stable id a person cites, e.g. `R-042` or `H-007`."""
        return f"{'R' if self.kind == 'refinements' else 'H'}-{self.number:03d}"

    @property
    def group(self) -> str:
        """Return the area (refinements) or sitting (host) this task belongs to."""
        return self.fields.get("Area") or self.fields["Sitting"]


def parse_status(raw: str) -> Status:
    """Parse a **Status:** value, or raise when it is outside the grammar."""
    if raw.startswith("open,"):
        state = raw[len("open,") :].strip()
        if state not in OPEN_STATES:
            msg = f"unknown open state {state!r}; expected one of {sorted(OPEN_STATES)}"
            raise TaskFileError(msg)
        return Status(state=state, on=None, detail="")
    if raw == "never attempted":
        return Status(state=raw, on=None, detail="")
    if raw.startswith(STANDING):
        _, sep, why = raw.partition(":")
        if not sep or not why.strip():
            msg = f"a standing status must read 'standing: <why it never closes>': {raw!r}"
            raise TaskFileError(msg)
        return Status(state=STANDING, on=None, detail=why.strip())
    head, _, rest = raw.partition(" ")
    if head in CLOSED_VERBS or head == "done":
        return Status(state=head, on=_parse_date(rest, raw), detail="")
    if head == "attempted":
        stamp, sep, detail = rest.partition(", inconclusive:")
        if not sep or not detail.strip():
            msg = (
                "an attempted status must read "
                f"'attempted <date>, inconclusive: <what happened>': {raw!r}"
            )
            raise TaskFileError(msg)
        return Status(state=head, on=_parse_date(stamp, raw), detail=detail.strip())
    msg = f"unknown status {raw!r}"
    raise TaskFileError(msg)


def _parse_date(text: str, raw: str) -> date:
    """Return the ISO date in ``text``, or raise naming the whole status line."""
    try:
        return date.fromisoformat(text.strip())
    except ValueError as err:
        msg = f"status {raw!r} needs a real YYYY-MM-DD date: {err}"
        raise TaskFileError(msg) from err


def _read_header(text: str) -> tuple[str, dict[str, str]]:
    """Return the H1 title and the field block that follows it.

    A field wraps like every other line of prose here, and the block ends where markdown ends its
    paragraph, at a blank line. Reading only a field's first line would render a long value
    truncated mid-sentence while the file itself, opened, reads whole.
    """
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# ") or not lines[0][2:].strip():
        msg = "the first line must be a non-empty '# Title'"
        raise TaskFileError(msg)
    title = lines[0][2:].strip()
    fields: dict[str, str] = {}
    last = ""
    for line in lines[1:]:
        if not line.strip():
            if fields:
                break  # the blank line that closes the block and opens the body
            continue  # the blank line between the title and the block
        match = FIELD.match(line)
        if match is None:
            if line.startswith("**"):
                # `**` opens a field in this block, so a mistyped one must fail here rather
                # than wrap into the field above it and be read as part of its value.
                msg = f"{line.strip()!r} is not a field line; expected '**Name:** value'"
                raise TaskFileError(msg)
            if not fields:
                break  # prose where the block should start; the missing-field check names it
            fields[last] = f"{fields[last]} {line.strip()}"
            continue
        last, value = match.group(1), match.group(2)
        if last in fields:
            msg = f"field {last!r} is given twice"
            raise TaskFileError(msg)
        fields[last] = value
    return title, fields


def _check_fields(kind: str, fields: dict[str, str]) -> None:
    """Raise when the field block is missing a required field or carries an unknown one."""
    required, optional = KIND_FIELDS[kind]
    for name in required:
        if name not in fields:
            msg = f"missing required field {name!r}"
            raise TaskFileError(msg)
    allowed = set(required) | set(optional)
    unknown = sorted(set(fields) - allowed)
    if unknown:
        msg = f"unknown field(s) {unknown}; allowed here: {sorted(allowed)}"
        raise TaskFileError(msg)


def _check_consistency(kind: str, title: str, status: Status, fields: dict[str, str]) -> None:
    """Raise when the kind, the title, the status and the remaining fields disagree."""
    if status.is_standing and kind != "host":
        msg = "a standing status belongs to the host backlog; a refinement is work that closes"
        raise TaskFileError(msg)
    lowered = title.lower()
    for banned in TITLE_BANS:
        if banned in lowered:
            msg = f"the title states a status ({banned!r}); status lives on the Status line alone"
            raise TaskFileError(msg)
    if TITLE_YEAR.search(title):
        msg = "the title carries a date; a date belongs on the Status line or in the Trail"
        raise TaskFileError(msg)
    trigger = fields.get("Trigger")
    if trigger is not None and not status.is_open:
        msg = "a closed task may not carry a Trigger"
        raise TaskFileError(msg)
    if trigger is None and status.state in NEEDS_TRIGGER:
        msg = f"a {status.state!r} task must name the Trigger that would reopen it"
        raise TaskFileError(msg)
    capability = fields.get("Capability")
    if capability is not None and capability not in CAPABILITIES:
        msg = f"capability {capability!r} is not one of {list(CAPABILITIES)}"
        raise TaskFileError(msg)


def parse_task(kind: str, path: Path, text: str) -> Task:
    """Parse one task file, or raise `TaskFileError` naming what is wrong with it."""
    match = FILENAME.match(path.name)
    if match is None:
        msg = "the file name must be NNN-a-hyphenated-slug.md"
        raise TaskFileError(msg)
    title, fields = _read_header(text)
    _check_fields(kind, fields)
    status = parse_status(fields["Status"])
    _check_consistency(kind, title, status, fields)
    return Task(
        kind=kind,
        number=int(match.group(1)),
        slug=match.group(2),
        path=path,
        title=title,
        status=status,
        fields=fields,
    )


def load(directory: Path, kind: str) -> list[Task]:
    """Parse every task file in ``directory``, ordered by number."""
    tasks: list[Task] = []
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as err:
            # A directory named like a task file, or bytes that are not text. The stray scan
            # names both too, so the gate reports this rather than failing while reading it.
            msg = f"{path}: cannot be read as a task file: {err}"
            raise TaskFileError(msg) from err
        try:
            tasks.append(parse_task(kind, path, text))
        except TaskFileError as err:
            msg = f"{path}: {err}"
            raise TaskFileError(msg) from err
    seen: dict[int, Path] = {}
    for task in tasks:
        if task.number in seen:
            msg = f"{task.path}: number {task.number:03d} is already used by {seen[task.number]}"
            raise TaskFileError(msg)
        seen[task.number] = task.path
    return tasks
