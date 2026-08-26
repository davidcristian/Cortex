"""Repo gate: fail when a subagent server this repo starts is missing a flag its tier requires.

The claim a reader wants about this tier is a claim about **every** server in it, and until this
scan the tree could only make the narrower one. The reasoning-off pair was held as a needle per
named compose file, so the two servers written down really did carry both flags, and a third
server added tomorrow in a new override carried whatever its author remembered and reddened
nothing. The set is what was missing, and `subagentservers.py` is where it is now derived from the
stack's own wiring and argv rather than registered by hand beside a check.

**What a fault costs, which is why the flags are worth a gate.** A subagent server started without
`--reasoning-budget 0` spends its whole token cap on a trace no reader ever sees and answers a cap
refusal (ADR-0005 switch-is-advisory addendum). One started without `--chat-template-kwargs
'{"enable_thinking": false}'` does the same on the plain requests the budget's own family does not
cover, the two flags reaching different halves of the request shapes this tier serves. One started
without `--jinja` cannot function-call at all, so a tools-enabled subagent loses its tools
(ADR-0010). None of the three is a crash. Each is a server that comes up healthy, passes its
healthcheck, and is wrong in a way whose only symptom is a slow or empty subagent, which is
exactly the failure a gate is for and a test is not.

**The requirements are grouped by the reason they exist, and a flag pair is one group.** Two flags
that must travel together are one claim about a deployment, not two, so they are written as one
requirement carrying one sentence, and a fault names that sentence whichever half went missing.
This is the same reading the constant registry took when it held the pair as a single needle
rather than inventing a relation for co-occurrence.

**A value is held at every occurrence, not the first.** llama.cpp takes the last spelling of a
repeated flag, so a server carrying `--reasoning-budget 0 --reasoning-budget 512` runs at 512
while a reader of its first pair believes otherwise, and a check that stopped at the first would
call that server compliant.

**The count under `--reasoning-budget` is one value in two trees**, this rule's and the model
host's `_NO_REASONING_BUDGET`, and `crosscheck.py` holds them together. So the sidecar's own
hosted subagent tier and the compose servers here cannot drift into disagreeing about what
"no thought" is, which matters because a narrow subtask wants none rather than a short one.

**Both floors are asserted**: a rule requiring no flag and a tree starting no subagent server are
each reported rather than passed, since a scan over nothing would report success forever.
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from composefiles import ComposeSearchError
from composestarts import ComposeStartError
from subagentservers import Server, servers

# A gate over no server, or over no requirement, would be green forever, which is the one thing
# every scan here refuses.
MIN_SERVERS = 1
MIN_FLAGS = 1


class FlagCheckError(Exception):
    """The servers a stack starts, or the flags they must carry, cannot be read or are empty."""


class Flag(NamedTuple):
    """One flag a server must start with, and the value that must follow it, where one must.

    ``value`` is None for a flag that takes none, which is the whole of what is asked of it: it
    is there or it is not.
    """

    name: str
    value: str | None = None


class Requirement(NamedTuple):
    """One thing every subagent server must be started with, and why every one of them must."""

    label: str
    why: str
    flags: tuple[Flag, ...]


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        label="the tool-capable chat template",
        why=(
            "a subagent server started without it runs llama.cpp's built-in template instead of "
            "the model's own, which cannot emit a tool call, so a tools-enabled subagent comes up "
            "healthy and silently has no tools (ADR-0010)"
        ),
        flags=(Flag("--jinja"),),
    ),
    Requirement(
        label="the tier's reasoning-off pair",
        why=(
            "every subagent server this repo starts carries both flags, because neither alone "
            "covers both request shapes the tier serves: the kwarg is what a chat template reads "
            "on a plain request, and the budget is what reaches the constrained shape every "
            "tool-less subagent decodes into the fixed envelope, where the kwarg was measured to "
            "stop holding. A server started with half the pair spends its whole token cap on a "
            "trace no reader ever sees and answers a cap refusal, which is a defect whose only "
            "symptom is a slow subagent (ADR-0005 switch-is-advisory addendum)"
        ),
        # The budget's count is the model host's `_NO_REASONING_BUDGET`, held to this spelling by
        # the constant scan, so the hosted tier and the compose servers cannot disagree about it.
        # Zero rather than a count, because a narrow subtask wants no thought and not a short one.
        flags=(
            Flag("--chat-template-kwargs", '{"enable_thinking": false}'),
            Flag("--reasoning-budget", "0"),
        ),
    ),
)


class Fault(NamedTuple):
    """One server started without something its tier requires, and what is wrong with it."""

    file: str
    service: str
    detail: str


class Scan(NamedTuple):
    """One run: what it was over, then what it could not account for."""

    servers: int
    files: int
    flags: int
    faults: list[Fault]


def missing(command: tuple[str, ...], flag: Flag) -> str | None:
    """What is wrong with one flag in one argv, or None when the argv carries it as required."""
    written = [
        command[index + 1] if index + 1 < len(command) else None
        for index, item in enumerate(command)
        if item == flag.name
    ]
    if not written:
        return f"it carries no {flag.name}"
    if flag.value is None:
        return None
    wrong = [value for value in written if value != flag.value]
    if not wrong:
        return None
    return f"{flag.name} is followed by {wrong[0]!r} where the tier requires {flag.value!r}"


def check_one(server: Server, requirements: tuple[Requirement, ...] | None = None) -> list[Fault]:
    """Every requirement one server's argv does not meet, in the order they are written here."""
    required = REQUIREMENTS if requirements is None else requirements
    return [
        Fault(server.file, server.service, f"{requirement.label}: {wrong}; {requirement.why}")
        for requirement in required
        for flag in requirement.flags
        if (wrong := missing(server.command, flag)) is not None
    ]


def check(root: Path, requirements: tuple[Requirement, ...] | None = None) -> Scan:
    """Hold every subagent server the compose tree under ``root`` starts to every requirement."""
    required = REQUIREMENTS if requirements is None else requirements
    flags = sum(len(requirement.flags) for requirement in required)
    if flags < MIN_FLAGS:
        msg = "no flag is required of a subagent server, and a rule over nothing cannot fail"
        raise FlagCheckError(msg)
    try:
        found = servers(root)
    except (ComposeStartError, ComposeSearchError) as err:
        raise FlagCheckError(str(err)) from err
    if len(found) < MIN_SERVERS:
        msg = f"no subagent server is started under {root}; a scan over nothing cannot fail"
        raise FlagCheckError(msg)
    return Scan(
        servers=len(found),
        files=len({server.file for server in found}),
        flags=flags,
        faults=[fault for server in found for fault in check_one(server, required)],
    )


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a subagent server this repo starts is missing a required flag.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the compose files that start the servers (default: .)",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"flagcheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given)
    except FlagCheckError as err:
        print(f"flagcheck: {err}", file=sys.stderr)
        return 2
    for fault in scanned.faults:
        print(f"{fault.file}: {fault.service}: {fault.detail}")
    if scanned.faults:
        print(
            f"\nflagcheck: {len(scanned.faults)} server problem(s). Every server the subagent "
            "wiring dials is started by a command in this tree, so add the flag to that command "
            "rather than to the deployment that remembers it.",
            file=sys.stderr,
        )
        return 1
    print(
        f"flagcheck OK: the {scanned.servers} subagent server(s) started under {given} by "
        f"{scanned.files} compose file(s) each carry all {scanned.flags} required flag(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
