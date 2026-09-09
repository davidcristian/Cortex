"""The couplings over the two llama.cpp images this repo starts servers from.

One of the data files `crosscheck.py` reads as a single registry. Like `emailcouplings.py` and
`fixturecouplings.py`, it arrived as a subject rather than as a split under the 300-line cap: a new
part is a data file plus one line in `registry.py`. Its subject is the engine image itself, which
is neither a tier setting nor a budget nor a fixture, and which is written as a mutable tag
everywhere it appears, so the name is the whole of what these places have to agree on.

Most of the deployment's spellings are already held, and by another gate. `volumecheck.py` compares
every compose service's image and every built stage's base against the rows `imagevolumes.py`
records, so a retag that moves one of them alone fails twice over, once for an image the record has
no row for and once for a recorded row nothing names. What that leaves uncovered is the four
spellings here: the builder stage of `brain/Dockerfile.modelhost`, which `dockerfilebases.py` skips
because only a final stage's config survives a build, and the three live harnesses, each of which
types an image and runs `docker run` on it. Until this part they floated, so a retag on the stack
left every harness starting containers from the old tag with every gate green (the ADR-0004
image-coupling addendum).

The declaring side of both entries is a measurement harness, which is the argument
`fixturecouplings.py` makes for its own subject: an `integration`-marked suite runs when somebody
chooses to measure, so nothing else would report the drift until a matrix came back describing a
build the stack stopped running.
"""

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
            "deployment runs and publishing the number under the build they name (ADR-0004 "
            "image-coupling addendum)"
        ),
        sites=(
            Site(INJECTION_HARNESS, "_GPU_IMAGE"),
            Site(CORRECTION_HARNESS, "_IMAGE"),
            Site(UID_HARNESS, "_IMAGE"),
        ),
        # Both `FROM` lines, one needle each, and each needle carrying what closes its own line:
        # the stage name after the builder's base and the line break after the final one. A tag
        # is written with hyphens and a hyphen is not a word character, so the bare needle `FROM
        # <tag>` goes on matching a line retagged to `<tag>-b10680` and the whole entry passes a
        # retag it exists to report. The builder stage is also the reason this file is here at
        # all: `dockerfilebases.py` reads the final stage's base alone, only that stage's config
        # surviving a build, and the two must move together or the workspace is installed against
        # one base image's interpreter and run on another's.
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
            "measuring something else (ADR-0004 image-coupling addendum)"
        ),
        sites=(Site(INJECTION_HARNESS, "_CPU_IMAGE"),),
        # One needle per file rather than one counted needle over the three, because these are
        # three independent services: a stack that gains a second CPU server is an addition, and
        # a file that stops naming the image at all is what this reports.
        mentions=(
            Mention(SUBAGENTS_COMPOSE, 'image: "{value}"'),
            Mention(ROSTER_COMPOSE, 'image: "{value}"'),
            Mention(MEMORY_COMPOSE, 'image: "{value}"'),
        ),
    ),
)
