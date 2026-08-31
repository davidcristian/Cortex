"""Tests for the stage reader that answers which image a Dockerfile in this tree stands on.

Most of these assert a raise. A guessed `FROM` names the wrong base, and the record would then
report the wrong image's declarations for whatever is built from that file. The tests that assert
an answer cover which stage decides: the last one, and what it stands on when that is an earlier
stage rather than an image.

The rule over this reader is exercised where it runs, through `undeclared` in
`test_dockerfilevolumes.py`, its one caller and the one place a base row meets a built row.
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
    """The last `FROM` decides, and an earlier builder stage does not.

    Measured with docker: only the final stage's config survives a build, so what an earlier stage
    declares reaches no container and its base needs no row in the record.
    """
    text = "FROM builder-image:1 AS builder\nFROM runtime-image:1\nCOPY --from=builder /a /a\n"
    assert read_base(text) == "runtime-image:1"


def test_a_final_stage_standing_on_an_earlier_stage_is_followed_back_to_the_image() -> None:
    """A final stage naming an earlier stage is followed back to the image that stage stands on.

    The build pulls that image, so a reader stopping at the stage name would look up a record row
    for a reference no registry serves.
    """
    text = "FROM real-image:1 AS base\nFROM base AS middle\nFROM middle\n"
    assert read_base(text) == "real-image:1"


def test_a_stage_name_is_matched_however_either_side_cases_it() -> None:
    """Stage names are matched case-insensitively.

    Docker matches them that way, so a case-sensitive reader would follow the chain to the wrong
    image.
    """
    assert read_base("from real-image:1 as Base\nFROM bAsE\n") == "real-image:1"


def test_a_flag_on_the_instruction_is_dropped_rather_than_read_as_the_image() -> None:
    assert read_base("FROM --platform=linux/amd64 real-image:1\n") == "real-image:1"


def test_a_stage_split_across_a_continuation_is_read_whole() -> None:
    assert read_base("FROM \\\n  real-image:1 \\\n  AS base\nFROM base\n") == "real-image:1"


def test_a_file_standing_on_scratch_stands_on_nothing() -> None:
    """A `scratch` base reads as no base, since no registry serves it and no build pulls it."""
    assert read_base("FROM scratch\nVOLUME /a\n") is None


def test_a_stage_reached_through_a_name_may_itself_stand_on_scratch() -> None:
    assert read_base("FROM scratch AS base\nFROM base\n") is None


# ── what it refuses ────────────────────────────────────────────────────────────


def test_a_file_with_no_from_at_all_is_refused() -> None:
    """A file with no `FROM` raises, since nothing in it says what the build stands on."""
    with pytest.raises(DockerfileError, match="no FROM instruction"):
        read_base("VOLUME /a\n")


def test_an_image_spelled_through_a_substitution_is_refused() -> None:
    """A base named through a variable substitution raises.

    Only a build resolves the substitution, and the record is keyed on the reference a build
    actually pulls.
    """
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
    """A stage that names itself raises.

    No build resolves it, and reading the name as an image would look up a record row for a stage
    name.
    """
    with pytest.raises(DockerfileError, match="stands on itself"):
        read_base("FROM loop AS loop\n")


def test_a_stage_standing_on_one_written_after_it_is_refused() -> None:
    """A stage naming a stage written after it raises.

    Docker resolves stage names only backwards, so it reads a forward reference as an image name
    while this reader has already seen the stage. The walk raises rather than picking one of the
    two readings.
    """
    with pytest.raises(DockerfileError, match="stands on itself or on one written after it"):
        read_base("FROM later AS first\nFROM real-image:1 AS later\nFROM first\n")


# ── the tree this reader is pointed at ─────────────────────────────────────────


def test_this_repos_own_dockerfiles_stand_on_the_two_bases_the_record_holds() -> None:
    """The two Dockerfiles in this repo read as the two bases the record holds.

    This guards the fixtures above: the shapes they exercise have to be the shapes the tree
    actually uses. Both files carry a builder stage, and neither builder base is the answer.
    """
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
