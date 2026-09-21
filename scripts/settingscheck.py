"""Fail when a setting a brain module reads is in no compose file for the service running it."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple, cast

from composefiles import ComposeSearchError, compose_files
from composeservices import ComposeServiceError, read_services
from composestarts import ComposeStartError, read_starts
from dockerfilevolumes import landings
from moduleconstants import ModuleReadError
from settingsfields import Settings, SettingsReadError, module_directory, read_settings

MODULE_FLAG = "-m"
_CMD = re.compile(r"^CMD\s+(?P<argv>.*?)\s*$")

MIN_CLASSES = 1


class Exemption(NamedTuple):
    """One setting deliberately named by no compose file, and why."""

    name: str
    why: str


EXEMPT = (
    Exemption(
        "CORTEX_SEAM_PORT",
        "the base file's port publish and healthcheck both fix the gRPC port at 50051, so a value "
        "passed in would move the listener away from both",
    ),
    Exemption(
        "CORTEX_TOOLS_ENDPOINT",
        "the single-sidecar form, which each tool overlay replaces with its own "
        "CORTEX_TOOLS_ENDPOINTS__<name> key and which the brain refuses beside those",
    ),
    Exemption(
        "CORTEX_MODELHOST_CORTEX_PORT",
        "the brain's CORTEX_INFERENCE_ENDPOINT in the gpu overlay dials the cortex tier at 8080",
    ),
    Exemption(
        "CORTEX_MODELHOST_BRAIN_PORT",
        "the brain's CORTEX_BRAIN_ENDPOINT in the gpu overlay dials the deep tier at 8081",
    ),
    Exemption(
        "CORTEX_MODELHOST_SUBAGENT_GPU_PORT",
        "the gpu overlay's documented CORTEX_SUBAGENTS_GPU_ENDPOINT dials that tier at 8083, and "
        "the loopback overlay moves only the host side of it",
    ),
    Exemption(
        "CORTEX_MODELHOST_LLAMA_BIN",
        "brain/Dockerfile.modelhost builds on the llama.cpp image, which fixes /app/llama-server",
    ),
    Exemption(
        "CORTEX_MODELHOST_MODELS_ROOT",
        "the gpu overlay mounts the models read-only at /models, the default this names",
    ),
)


class SettingsCheckError(Exception):
    """The stack, or the settings it is compared against, cannot be read, or the set is empty."""


class Fault(NamedTuple):
    """One setting a service does not receive, or one exemption that no longer holds."""

    where: str
    detail: str


class Scan(NamedTuple):
    """What one run read, and what it could not account for."""

    services: tuple[str, ...]
    classes: int
    fields: int
    files: int
    faults: list[Fault]


def module_run(argv: tuple[str, ...]) -> str | None:
    """The module an argv runs with `-m`, or None when it runs none."""
    for index, word in enumerate(argv[:-1]):
        if word == MODULE_FLAG:
            return argv[index + 1]
    return None


def image_command(dockerfile: Path) -> tuple[str, ...] | None:
    """The argv the last `CMD` of a Dockerfile starts its image with, None when it has none."""
    written = None
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        if (found := _CMD.match(line.strip())) is not None:
            written = found.group("argv")
    if written is None:
        return None
    try:
        loaded: object = json.loads(written)
    except json.JSONDecodeError as err:
        msg = f"{dockerfile}: CMD {written!r} is not the exec form this scan reads"
        raise SettingsCheckError(msg) from err
    if not isinstance(loaded, list):
        msg = f"{dockerfile}: CMD {written!r} is not a list"
        raise SettingsCheckError(msg)
    return tuple(str(word) for word in cast("list[object]", loaded))


class Stack(NamedTuple):
    """Every compose file read together: each service's argv, and the keys in its environment."""

    files: int
    argv: dict[str, tuple[str, ...]]
    keys: dict[str, frozenset[str]]


def read_stack(root: Path) -> Stack:
    """Read every compose file under ``root``, merging each service across the files naming it."""
    argv: dict[str, tuple[str, ...]] = {}
    keys: dict[str, set[str]] = {}
    built: dict[str, list[Path]] = {}
    paths = compose_files(root)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for started in read_starts(text):
            keys.setdefault(started.service, set()).update(key for key, _ in started.environment)
            if started.command is None:
                continue
            if argv.setdefault(started.service, started.command) != started.command:
                msg = f"{started.service} is started with two different commands across the files"
                raise SettingsCheckError(msg)
        for service in read_services(text).services:
            if service.build is not None:
                built.setdefault(service.name, landings(root, path, service.build))
    for name, landed in built.items():
        if name not in argv and landed and (command := image_command(landed[0])) is not None:
            argv[name] = command
    return Stack(len(paths), argv, {name: frozenset(named) for name, named in keys.items()})


def held(root: Path, stack: Stack) -> dict[str, Settings]:
    """Each service that runs a workspace module, with the settings that module reads."""
    found: dict[str, Settings] = {}
    for service, command in sorted(stack.argv.items()):
        module = module_run(command)
        directory = None if module is None else module_directory(root, module)
        if directory is not None:
            found[service] = read_settings(root, directory)
    return found


def judge(
    services: dict[str, Settings], stack: Stack, exempt: tuple[Exemption, ...]
) -> list[Fault]:
    """Every field no file names for the service reading it, and every exemption gone stale."""
    reasons = {exemption.name: exemption.why for exemption in exempt}
    faults: list[Fault] = []
    declared: set[str] = set()
    for service, settings in services.items():
        keys = stack.keys.get(service, frozenset())
        for field in settings.fields:
            declared.add(field.name)
            where = f"{field.file}: {field.owner}.{field.name}"
            if field.named_by(keys) and field.name in reasons:
                detail = f"is exempt, yet a compose file names it for {service}; drop the exemption"
                faults.append(Fault(where, detail))
            elif not field.named_by(keys) and field.name not in reasons:
                detail = f"reaches the {service} service from no compose file; add it as a bare key"
                faults.append(Fault(where, detail))
    faults.extend(
        Fault(
            "settingscheck.EXEMPT", f"{name} is exempt, but no settings class read here declares it"
        )
        for name in reasons
        if name not in declared
    )
    return faults


def check(root: Path, exempt: tuple[Exemption, ...] = EXEMPT) -> Scan:
    """Check every service that runs a workspace module against the settings that module reads."""
    try:
        stack = read_stack(root)
        services = held(root, stack)
    except (
        ComposeSearchError,
        ComposeServiceError,
        ComposeStartError,
        ModuleReadError,
        SettingsReadError,
        OSError,
    ) as err:
        raise SettingsCheckError(str(err)) from err
    classes = sum(len(settings.classes) for settings in services.values())
    if classes < MIN_CLASSES:
        msg = (
            f"no service under {root} runs a module with settings; a scan over nothing cannot fail"
        )
        raise SettingsCheckError(msg)
    return Scan(
        services=tuple(services),
        classes=classes,
        fields=sum(len(settings.fields) for settings in services.values()),
        files=stack.files,
        faults=judge(services, stack, exempt),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the check; print any faults and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a setting a module reads reaches its service from no compose file.",
    )
    parser.add_argument("--root", type=Path, default=Path(), help="repo root (default: .)")
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"settingscheck: root {given} is not a directory", file=sys.stderr)
        return 2
    try:
        scanned = check(given)
    except SettingsCheckError as err:
        print(f"settingscheck: {err}", file=sys.stderr)
        return 2
    for fault in scanned.faults:
        print(f"{fault.where}: {fault.detail}")
    if scanned.faults:
        print(
            f"\nsettingscheck: {len(scanned.faults)} problem(s). A setting no compose file names "
            "never reaches the container, so name it as a bare key in the environment of the "
            "service that reads it, or exempt it in settingscheck.py with the reason.",
            file=sys.stderr,
        )
        return 1
    print(
        f"settingscheck OK: the {scanned.fields} field(s) of {scanned.classes} settings class(es) "
        f"read by {', '.join(scanned.services)} are each named in that service's environment by "
        f"one of {scanned.files} compose file(s), or exempt with a reason"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
