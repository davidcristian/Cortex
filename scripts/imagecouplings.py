"""The couplings over the two llama.cpp images this repo starts servers from."""

from couplings import Constant, Mention, Site

INJECTION_HARNESS = "brain/packages/inference/tests/test_injection_defense_live.py"
CORRECTION_HARNESS = "brain/packages/orchestrator/tests/test_unfenced_correction_live.py"
UID_HARNESS = "brain/packages/orchestrator/tests/test_uid_reading_live.py"
MODELHOST_DOCKERFILE = "brain/Dockerfile.modelhost"
SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
ROSTER_COMPOSE = "docker/docker-compose.subagents-roster.yml"
MEMORY_COMPOSE = "docker/docker-compose.memory.yml"

IMAGE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the CUDA engine image",
        why=(
            "this is the image the model host is built from and the image all three live "
            "harnesses start a card row's server from, and each of the four spells it out, so a "
            "retag of the engine the stack runs leaves those harnesses measuring a build no "
            "deployment runs and publishing the number under the build they name (ADR-0060 "
            "decision 5)"
        ),
        sites=(
            Site(INJECTION_HARNESS, "_GPU_IMAGE"),
            Site(CORRECTION_HARNESS, "_IMAGE"),
            Site(UID_HARNESS, "_IMAGE"),
        ),
        mentions=(
            Mention(MODELHOST_DOCKERFILE, "FROM {value} AS builder"),
            Mention(MODELHOST_DOCKERFILE, "FROM {value}\n"),
        ),
    ),
    Constant(
        label="the CPU engine image",
        why=(
            "three compose services run this image, the two subagent servers and the embedder, "
            "and the injection harness starts its CPU rows from it, so a retag on the stack "
            "alone leaves the placement row that exists to measure what a stock deployment runs "
            "measuring something else (ADR-0060 decision 5)"
        ),
        sites=(Site(INJECTION_HARNESS, "_CPU_IMAGE"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, 'image: "{value}"'),
            Mention(ROSTER_COMPOSE, 'image: "{value}"'),
            Mention(MEMORY_COMPOSE, 'image: "{value}"'),
        ),
    ),
)
