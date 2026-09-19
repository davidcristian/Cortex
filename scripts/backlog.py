"""Read and check the per-task backlog files under `docs/refinements` and `docs/host`."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FILENAME = re.compile(r"^(\d{3})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
FIELD = re.compile(r"^\*\*([A-Za-z]+):\*\* +(.+?) *$")
# "done" and "closed" are left out: both are ordinary adjectives in a title, which the substring
# check would reject.
TITLE_BANS = ("declined", "satisfied")
TITLE_YEAR = re.compile(r"\b(19|20)\d{2}\b")

OPEN_STATES = {
    "actionable": "Actionable now",
    "needs a port change first": "Actionable, once a port changes",
    "waiting for its trigger": "Waiting for its trigger",
    "waiting for a consumer": "Waiting for a consumer",
    "optional feature": "Optional feature, on request",
    "blocked on host hardware": "Blocked on hardware this repo is not developed on",
}
NEEDS_TRIGGER = frozenset({"waiting for its trigger", "waiting for a consumer"})
UNRECORDED = "unrecorded"
CLOSED_VERBS = ("done", "declined", "satisfied")

HOST_STATES = ("never attempted", "attempted", "done")
ONGOING = "ongoing"

KIND_FIELDS = {
    "refinements": (("Status", "Area", "Origin"), ("Trigger", "Verified")),
    "host": (("Status", "Session", "Capability", "Origin"), ("Verified",)),
}
CAPABILITIES = ("W", "G", "W+G")


class TaskFileError(Exception):
    """A task file does not follow the layout the readers and the index rely on."""


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
    def is_ongoing(self) -> bool:
        """Return True when the task never closes, so no count may call it open or closed."""
        return self.state == ONGOING

    @property
    def bucket(self) -> str:
        """Return the index heading this status files under."""
        if self.state in OPEN_STATES:
            return OPEN_STATES[self.state]
        if self.state == "never attempted":
            return "Never attempted"
        if self.state == "attempted":
            return "Attempted, inconclusive"
        if self.state == ONGOING:
            return "Ongoing, never closes"
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
        """Return the area (refinements) or session (host) this task belongs to."""
        return self.fields.get("Area") or self.fields["Session"]


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
    if raw.startswith(ONGOING):
        _, sep, why = raw.partition(":")
        if not sep or not why.strip():
            msg = f"an ongoing status must read 'ongoing: <why it never closes>': {raw!r}"
            raise TaskFileError(msg)
        return Status(state=ONGOING, on=None, detail=why.strip())
    head, _, rest = raw.partition(" ")
    if head in CLOSED_VERBS:
        return Status(state=head, on=_parse_date(rest, f"status {raw!r}"), detail="")
    if head == "attempted":
        stamp, sep, detail = rest.partition(", inconclusive:")
        if not sep or not detail.strip():
            msg = (
                "an attempted status must read "
                f"'attempted <date>, inconclusive: <what happened>': {raw!r}"
            )
            raise TaskFileError(msg)
        return Status(state=head, on=_parse_date(stamp, f"status {raw!r}"), detail=detail.strip())
    msg = f"unknown status {raw!r}"
    raise TaskFileError(msg)


def _parse_date(text: str, subject: str) -> date:
    """Return the ISO date in ``text``, or raise naming the whole line ``subject`` describes."""
    try:
        return date.fromisoformat(text.strip())
    except ValueError as err:
        msg = f"{subject} needs a real YYYY-MM-DD date: {err}"
        raise TaskFileError(msg) from err


def _read_header(text: str) -> tuple[str, dict[str, str]]:
    """Return the H1 title and the field block that follows it."""
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
                break
            continue
        match = FIELD.match(line)
        if match is None:
            if line.startswith("**"):
                msg = f"{line.strip()!r} is not a field line; expected '**Name:** value'"
                raise TaskFileError(msg)
            if not fields:
                break
            fields[last] = f"{fields[last]} {line.strip()}"
            continue
        last, value = match.group(1), match.group(2)
        if last in fields:
            msg = f"field {last!r} is given twice"
            raise TaskFileError(msg)
        fields[last] = value
    return title, fields


def _check_fields(kind: str, fields: dict[str, str]) -> None:
    """Raise when the field block is missing a required field or has an unknown one."""
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
    if status.is_ongoing and kind != "host":
        msg = "an ongoing status belongs to the host backlog; a refinement is work that closes"
        raise TaskFileError(msg)
    lowered = title.lower()
    for banned in TITLE_BANS:
        if banned in lowered:
            msg = f"the title states a status ({banned!r}); status lives on the Status line alone"
            raise TaskFileError(msg)
    if TITLE_YEAR.search(title):
        msg = "the title states a date; a date belongs on the Status line or under History"
        raise TaskFileError(msg)
    trigger = fields.get("Trigger")
    if trigger is not None and not status.is_open:
        msg = "a closed task may not have a Trigger"
        raise TaskFileError(msg)
    if trigger is None and status.state in NEEDS_TRIGGER:
        msg = f"a {status.state!r} task must name the Trigger that would reopen it"
        raise TaskFileError(msg)
    verified = fields.get("Verified")
    if verified is not None and not status.is_open:
        state = "an ongoing" if status.is_ongoing else "a closed"
        msg = f"{state} task may not have a Verified date"
        raise TaskFileError(msg)
    if verified is not None:
        _parse_date(verified, f"the Verified line {verified!r}")
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
