"""Fail when a subagent server this repo starts is missing a flag its tier requires."""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from artifactnames import Artifact, named
from composefiles import ComposeSearchError
from composestarts import ComposeStartError
from hostedtiers import HostedTierError, hosted
from subagentflags import REQUIREMENTS, Requirement, applies, missing
from subagentservers import FAMILY_PREFIX, Server, servers

MIN_SERVERS = 1
MIN_FLAGS = 1


class FlagCheckError(Exception):
    """The servers a stack starts, or the flags they need, cannot be read or are empty."""


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
    """What one run checked, and what it could not account for."""

    servers: int
    files: int
    flags: int
    artifacts: int
    faults: list[Fault]


def check_one(server: Server, requirements: tuple[Requirement, ...] | None = None) -> list[Fault]:
    """Every requirement one server's argv does not meet, in the order the rules are written."""
    required = REQUIREMENTS if requirements is None else requirements
    return [
        Fault(server.file, server.service, f"{requirement.label}: {wrong}; {requirement.why}")
        for requirement in required
        if applies(server.command, requirement)
        for flag in requirement.flags
        if (wrong := missing(server.command, flag)) is not None
    ]


def unclassifiable(artifact: Artifact) -> Fault | None:
    """What is wrong with one model artifact's name, or None when the readers can classify it."""
    if artifact.variable.startswith(FAMILY_PREFIX):
        return None
    return Fault(
        artifact.file,
        artifact.where,
        f"the artifact naming rule: its model artifact is named under {artifact.variable}, which "
        f"does not begin {FAMILY_PREFIX}; {WHY_NAMED}",
    )


def check(root: Path, requirements: tuple[Requirement, ...] | None = None) -> Scan:
    """Check every subagent server the tree under ``root`` starts against every requirement."""
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
    """Run the check; print any faults and return the process exit code."""
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
        f"{scanned.files} file(s) each carry every one of the {scanned.flags} required flag(s) "
        f"that reaches them, and the "
        f"{scanned.artifacts} model artifact(s) this tree names are each named so a reader can "
        "say which tier they serve"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
