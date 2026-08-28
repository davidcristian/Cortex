"""Behaviour of the stage reader: which image a Dockerfile in this tree really stands on.

Almost everything here asserts a refusal, for the reason the sibling reader's tests do: a `FROM`
guessed at names the wrong base, and the wrong base is a row whose declarations the record would go
on denying about the image built from that file. The two tests that assert an answer rather than a
refusal are the ones that matter most, and they are about which stage decides: the last one, and
whatever it stands on when it stands on an earlier stage rather than on an image.

The rule over this reader is exercised where it runs, through `undeclared` in
`test_dockerfilevolumes.py`, which is the one caller and the one place a base row meets a built row.
"""

from pathlib import Path

import pytest

from dockerfilebases import DockerfileError, read_base
from imagevolumes import IMAGE_VOLUMES

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── which stage decides ────────────────────────────────────────────────────────


def test_a_single_stage_stands_on_the_image_it_names() -> None:
    assert read_base("FROM python:3.12-slim-trixie\nRUN true\n") == "python:3.12-slim-trixie"


def test_the_last_stage_decides_and_a_builder_stage_does_not() -> None:
    """Measured with docker: only the final stage's config survives a build, so what an earlier
    stage declares reaches no container and its base owes the record no row."""
    text = "FROM builder-image:1 AS builder\nFROM runtime-image:1\nCOPY --from=builder /a /a\n"
    assert read_base(text) == "runtime-image:1"


def test_a_final_stage_standing_on_an_earlier_stage_is_followed_back_to_the_image() -> None:
    """The name is a stage rather than an image, so the build really pulls what that stage stands
    on, and a reader stopping at the name would ask the record for a row nothing publishes."""
    text = "FROM real-image:1 AS base\nFROM base AS middle\nFROM middle\n"
    assert read_base(text) == "real-image:1"


def test_a_stage_name_is_matched_however_either_side_cases_it() -> None:
    """Docker does not care, so a reader that did would follow the chain to the wrong end."""
    assert read_base("from real-image:1 as Base\nFROM bAsE\n") == "real-image:1"


def test_a_flag_on_the_instruction_is_dropped_rather_than_read_as_the_image() -> None:
    assert read_base("FROM --platform=linux/amd64 real-image:1\n") == "real-image:1"


def test_a_stage_split_across_a_continuation_is_read_whole() -> None:
    assert read_base("FROM \\\n  real-image:1 \\\n  AS base\nFROM base\n") == "real-image:1"


def test_a_file_standing_on_scratch_stands_on_nothing() -> None:
    """A row for `scratch` would be a row for an image no registry serves and no build pulls."""
    assert read_base("FROM scratch\nVOLUME /a\n") is None


def test_a_stage_reached_through_a_name_may_itself_stand_on_scratch() -> None:
    assert read_base("FROM scratch AS base\nFROM base\n") is None


# ── what it refuses ────────────────────────────────────────────────────────────


def test_a_file_with_no_from_at_all_is_refused() -> None:
    """A fragment, or a file this reader misread; either way nothing says what it is built on."""
    with pytest.raises(DockerfileError, match="no FROM instruction"):
        read_base("VOLUME /a\n")


def test_an_image_spelled_through_a_substitution_is_refused() -> None:
    """Only a build resolves it, and the record is keyed on the reference a build really pulls."""
    with pytest.raises(DockerfileError, match="carries an expansion"):
        read_base("ARG BASE\nFROM ${BASE}\n")


@pytest.mark.parametrize(
    "argument",
    ["real-image:1 base", "real-image:1 NOT base", "real-image:1 AS base spare", "--platform=x"],
    ids=["no-as", "wrong-keyword", "trailing", "flag-only"],
)
def test_a_from_that_is_not_an_image_optionally_named_is_refused(argument: str) -> None:
    with pytest.raises(DockerfileError, match="is not an image"):
        read_base(f"FROM {argument}\n")


def test_a_stage_standing_on_itself_is_refused_rather_than_read_as_an_image() -> None:
    """No build could resolve it, and reading it as an image would ask for a row for a stage."""
    with pytest.raises(DockerfileError, match="stands on itself"):
        read_base("FROM loop AS loop\n")


def test_a_stage_standing_on_one_written_after_it_is_refused() -> None:
    """Docker resolves a stage name only backwards, so a forward reference is an image to it and a
    contradiction to this reader; the walk refuses rather than picking one of the two readings."""
    with pytest.raises(DockerfileError, match="stands on itself or on one written after it"):
        read_base("FROM later AS first\nFROM real-image:1 AS later\nFROM first\n")


# ── the tree this reader is pointed at ─────────────────────────────────────────


def test_this_repos_own_dockerfiles_stand_on_the_two_bases_the_record_holds() -> None:
    """A guard on every fixture above: the shapes it agrees with have to be the tree's shapes.
    Both files carry a builder stage, and neither builder base is the answer."""
    read = {
        name: (REPO_ROOT / name).read_text(encoding="utf-8")
        for name in ("brain/Dockerfile", "brain/Dockerfile.modelhost")
    }
    assert {name: read_base(text) for name, text in read.items()} == {
        "brain/Dockerfile": "python:3.12-slim-trixie",
        "brain/Dockerfile.modelhost": "ghcr.io/ggml-org/llama.cpp:server-cuda",
    }
    assert all("AS builder" in text for text in read.values()), read
    assert all(base in IMAGE_VOLUMES for base in {read_base(text) for text in read.values()})
