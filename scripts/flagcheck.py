"""Repo gate: fail when a subagent server this repo starts is missing a flag its tier requires.

The set of servers is derived rather than listed. `subagentservers.py` reads it off the compose
stack's own wiring and argv, and `hostedtiers.py` answers for the one placement no compose file
holds, the model host's hosted subagent tier. Neither reader says which flags matter: `REQUIREMENTS`
below is the whole rule and runs over the union of both sets, so a flag added here reaches both
placements. Both readers decide membership from the variable a model artifact is named under, so
`artifactnames.py` finds every such variable structurally and the rule below holds each to beginning
with `FAMILY_PREFIX`; a rule whose domain was the family itself could not fail for the misnaming it
exists to catch. The ADR-0029 addenda on deriving the set a rule runs over, on covering both
placements of one tier with one rule, and on holding the convention a derived set is read out of
argue all three choices.

A server started without `--reasoning-budget 0` spends its whole token cap on reasoning output no
caller reads, then answers a cap refusal (ADR-0005 switch-is-advisory addendum). One started without
`--chat-template-kwargs '{"enable_thinking": false}'` does the same on the plain requests the budget
does not cover, the two flags reaching different halves of the request shapes this tier serves. One
started without `--jinja` cannot function-call at all, so a tools-enabled subagent loses its tools
(ADR-0010). None of the three crashes: the server comes up healthy, passes its healthcheck, and the
only symptom is a slow or empty subagent.

Two flags that must travel together are written as one requirement carrying one sentence, so a
fault names that sentence whichever half is missing. A flag's value is checked at every occurrence
rather than the first, llama.cpp taking the last spelling of a repeated flag. Both floors are
asserted: a rule requiring no flag, and a tree starting no subagent server, are each reported
rather than passed.
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from artifactnames import Artifact, named
from composefiles import ComposeSearchError
from composestarts import ComposeStartError
from hostedtiers import HostedTierError, hosted
from subagentservers import FAMILY_PREFIX, Server, servers

# A gate over no server, or over no requirement, would be green forever, so every scan here fails
# when either set is empty.
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
        # Zero rather than a count, because a narrow subtask needs no thought and not a short one.
        flags=(
            Flag("--chat-template-kwargs", '{"enable_thinking": false}'),
            Flag("--reasoning-budget", "0"),
        ),
    ),
)


# Why an artifact's own name is this gate's business, printed with any naming fault exactly as a
# requirement prints why every server must meet it.
WHY_NAMED = (
    "both readers of this gate's set decide whether a server or a tier serves subagents from that "
    "spelling alone, so an artifact named another way drops out of the set unreported and this "
    "scan passes over the server or tier it belongs to"
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
    artifacts: int
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


def unclassifiable(artifact: Artifact) -> Fault | None:
    """What is wrong with one artifact's name, or None when a membership reader can classify it."""
    if artifact.variable.startswith(FAMILY_PREFIX):
        return None
    return Fault(
        artifact.file,
        artifact.where,
        f"the artifact naming rule: its model artifact is named under {artifact.variable}, which "
        f"does not begin {FAMILY_PREFIX}; {WHY_NAMED}",
    )


def check(root: Path, requirements: tuple[Requirement, ...] | None = None) -> Scan:
    """Hold every subagent server the tree under ``root`` starts, either way, to every requirement.

    The compose stack is read first, so a tree that is no repo at all is reported as the compose
    tree it is missing rather than as the sidecar module underneath that one.
    """
    required = REQUIREMENTS if requirements is None else requirements
    flags = sum(len(requirement.flags) for requirement in required)
    if flags < MIN_FLAGS:
        msg = "no flag is required of a subagent server, and a rule over nothing cannot fail"
        raise FlagCheckError(msg)
    try:
        composed = servers(root)
        tiers = hosted(root)
        artifacts = named(root)
    except (ComposeStartError, ComposeSearchError, HostedTierError) as err:
        raise FlagCheckError(str(err)) from err
    found = (
        *composed,
        *(
            Server(file=tier.file, service=tier.named, line=tier.line, command=tier.command)
            for tier in tiers
        ),
    )
    if len(found) < MIN_SERVERS:
        msg = f"no subagent server is started under {root}; a scan over nothing cannot fail"
        raise FlagCheckError(msg)
    return Scan(
        servers=len(found),
        files=len({server.file for server in found}),
        flags=flags,
        artifacts=len(artifacts),
        faults=[
            *(fault for server in found for fault in check_one(server, required)),
            *(fault for artifact in artifacts if (fault := unclassifiable(artifact)) is not None),
        ],
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
            f"\nflagcheck: {len(scanned.faults)} problem(s). Every subagent server this repo "
            "starts is started by an argv written in this tree, a compose command or the model "
            "host's own tier, and every model artifact one of them serves is named under a "
            f"{FAMILY_PREFIX} variable, so add the flag to that argv or spell the name that way "
            "rather than leaving either to the deployment that remembers it.",
            file=sys.stderr,
        )
        return 1
    print(
        f"flagcheck OK: the {scanned.servers} subagent server(s) started under {given} by "
        f"{scanned.files} file(s) each carry all {scanned.flags} required flag(s), and the "
        f"{scanned.artifacts} model artifact(s) this tree names are each named so a reader can "
        "say which tier they serve"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
