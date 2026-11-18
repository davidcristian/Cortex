"""What every subagent server this repo starts must be given, and how one argv is checked."""

from typing import NamedTuple


class Flag(NamedTuple):
    """One flag a server must start with, and the value that must follow it, where one is needed."""

    name: str
    value: str | None = None


class Requirement(NamedTuple):
    """One thing a subagent server must be started with, and why the servers it covers need it."""

    label: str
    why: str
    flags: tuple[Flag, ...]
    when: Flag | None = None


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
            "every subagent server this repo starts has both flags, because neither alone "
            "covers both request shapes the tier serves: the kwarg is what a chat template reads "
            "on a plain request, and the budget is what reaches the constrained shape every "
            "tool-less subagent decodes into the fixed envelope, where the kwarg was measured to "
            "stop holding. A server started with half the pair spends its whole token cap on a "
            "trace no reader ever sees and answers a cap refusal, which is a defect whose only "
            "symptom is a slow subagent (ADR-0049)"
        ),
        flags=(
            Flag("--chat-template-kwargs", '{"enable_thinking": false}'),
            Flag("--reasoning-budget", "0"),
        ),
    ),
    Requirement(
        label="the host-RAM prompt cache, turned off",
        why=(
            "llama.cpp keeps a prompt cache in host RAM for a conversation whose server slot has "
            "been taken and sizes it at 8192 MiB by default, which is the whole memory cap the "
            "compose subagent servers run under and a third of the one the model host's three "
            "tiers share. What such a cache grows into is the mapped weights a server reads on "
            "every token, measured on the shipped pick at 781 MiB of headroom spent in nine "
            "prompts and the weights reclaimed from the tenth on, so a subagent server left on "
            "the default answers more slowly the longer it runs and one on a full cgroup is "
            "killed outright. Zero was measured to cost nothing on this tier's one-shot subtasks "
            "(ADR-0059)"
        ),
        flags=(Flag("--cache-ram", "0"),),
    ),
    Requirement(
        label="a thread count on a server that offloads no layer",
        why=(
            "llama.cpp starts one thread per hardware thread, which is not what a server under a "
            "CPU quota may spend: left at that default the shipped CPU subagent server ran 24 "
            "threads inside its quota, was throttled in 14,308 of 14,520 periods and decoded at "
            "0.43 to 0.54 tok/s against 11.9 to 12.4 with the count set (ADR-0004 decision "
            "12). The flag is what is asked here and not the number after it: the "
            "right count is the service's own cpus cap, a relation between two keys of one "
            "compose file that the constant scan holds per file"
        ),
        when=Flag("-ngl", "0"),
        flags=(Flag("--threads"),),
    ),
    Requirement(
        label="the speculative type and draft length of a drafter file",
        why=(
            "a server given a multi-token-prediction drafter file without the type loads the "
            "drafter, which takes its memory on the card, and drafts nothing, as measured on the "
            "deep tier. Without a draft length it drafts at the engine's default and not at the "
            "length its tier was measured fastest at (ADR-0077 decision 7)"
        ),
        when=Flag("--model-draft"),
        flags=(Flag("--spec-type", "draft-mtp"), Flag("--spec-draft-n-max")),
    ),
    Requirement(
        label="a V cache type beside a K cache type",
        why=(
            "the engine holds keys and values in two types, each with its own flag, and the rule "
            "a tier is given an 8-bit cache on was read with both set. A server given the K type "
            "alone keeps its values at 16 bits, a shape that rule has no row for (ADR-0077 "
            "decision 8)"
        ),
        when=Flag("--cache-type-k"),
        flags=(Flag("--cache-type-v"),),
    ),
)


def missing(command: tuple[str, ...], flag: Flag) -> str | None:
    """What is wrong with one flag in one argv, or None when the argv has it as required."""
    written = [
        command[index + 1] if index + 1 < len(command) else None
        for index, item in enumerate(command)
        if item == flag.name
    ]
    if not written:
        return f"it has no {flag.name}"
    if flag.value is None:
        return None
    wrong = [value for value in written if value != flag.value]
    if not wrong:
        return None
    return f"{flag.name} is followed by {wrong[0]!r} where the tier requires {flag.value!r}"


def applies(command: tuple[str, ...], requirement: Requirement) -> bool:
    """Whether one requirement reaches one argv, which is every argv unless it names one."""
    return requirement.when is None or missing(command, requirement.when) is None
