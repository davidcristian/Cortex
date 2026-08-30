"""Behaviour of the re-derivation: how docker's answer is read back, and which rows have moved.

The record is a measurement, so most of what can go wrong with it is drift, and drift is what
`rederive` reports. Everything here drives it with a fake inspector, which is the whole reason the
comparison and the `docker image inspect` call are separate functions: the daemon is out of reach
in CI and on a clean dev box, and a comparison that could only be exercised through it would be a
comparison nothing checks. `parse` is the other half of that split, holding the shape a real
answer has to have, and it is tested on text rather than on a daemon for the same reason. The one
test that does reach a real docker is `integration`-marked and is what `just image-volumes` runs
for a living.
"""

from collections.abc import Mapping

import pytest

import imagedrift
from imagedrift import InspectError, docker_volumes, parse, rederive, render
from imagevolumes import IMAGE_VOLUMES, Row

FAKE: dict[str, Row] = {
    "dovecot/dovecot:2.3.21": Row(("/etc/dovecot", "/srv/mail"), ()),
    "redis:8-alpine": Row((), ()),
}


def _inspector(answers: Mapping[str, Row]) -> imagedrift.Inspector:
    """An inspector answering from a dict and refusing anything else, the way docker does."""

    def inspect(reference: str, *, pull: bool) -> Row:  # noqa: ARG001
        try:
            return answers[reference]
        except KeyError as err:
            msg = f"docker image inspect failed: no such image: {reference}"
            raise InspectError(msg) from err

    return inspect


# ── reading docker's answer back ───────────────────────────────────────────────


def test_an_image_declaring_both_kinds_is_read_into_both_dimensions() -> None:
    """The volumes come back sorted, since which paths are declared is the question; the triggers
    come back as written, since they fire in the order the image carries them."""
    answered = '{"/srv/mail":{},"/etc/dovecot":{}}\n["VOLUME /probe/onbuild","RUN true"]'
    assert parse(answered) == Row(
        ("/etc/dovecot", "/srv/mail"), ("VOLUME /probe/onbuild", "RUN true")
    )


def test_an_image_declaring_neither_answers_null_in_both_lines() -> None:
    """What every row in this repo's record says today, and it is an answer rather than a gap."""
    assert parse("null\nnull\n") == Row((), ())


def test_a_trigger_carrying_a_newline_stays_one_entry() -> None:
    """Why the format prints JSON rather than a line per entry: instruction text is arbitrary, and
    a line-oriented answer would read one trigger as two."""
    assert parse('null\n["RUN a\\nb"]') == Row((), ("RUN a\nb",))


@pytest.mark.parametrize(
    ("answered", "message"),
    [
        ("null", "answered in 1 line"),
        ("null\nnull\nnull", "answered in 3 line"),
        ("{oops}\nnull", "Config.Volumes is not the JSON"),
        ("null\n[", "Config.OnBuild is not the JSON"),
        ('["/a"]\nnull', "not an object of paths"),
        ('null\n{"a": 1}', "not a list of instructions"),
        ("null\n[7]", "which is not an instruction"),
    ],
)
def test_an_answer_the_reader_was_not_taught_is_refused(answered: str, message: str) -> None:
    """An answer nobody could read is a row that went unchecked, which is reported as drift rather
    than resolved to an image declaring nothing."""
    with pytest.raises(InspectError, match=message):
        parse(answered)


# ── how a report reads ─────────────────────────────────────────────────────────


def test_render_spells_an_empty_answer_in_words() -> None:
    assert (render(()), render(("/a", "/b"))) == ("nothing", "/a, /b")


# ── rederivation ───────────────────────────────────────────────────────────────


def test_a_record_docker_still_agrees_with_reports_nothing() -> None:
    assert rederive(FAKE, FAKE, _inspector(FAKE)) == []


def test_a_row_docker_has_stopped_agreeing_with_is_reported_both_ways_round() -> None:
    """The message carries both answers, because the fix is to edit one of them into the other."""
    moved = {**FAKE, "redis:8-alpine": Row(("/data",), ())}
    report = rederive(FAKE, FAKE, _inspector(moved))
    assert report == ["redis:8-alpine: recorded nothing, docker says /data"]


def test_a_base_that_has_gained_a_trigger_is_reported_as_the_dimension_it_moved_in() -> None:
    """The drift the trigger dimension exists to catch: `Config.Volumes` is empty and stays empty,
    and the base has started declaring a volume in whatever is built from it."""
    moved = {**FAKE, "redis:8-alpine": Row((), ("VOLUME /x",))}
    report = rederive(FAKE, FAKE, _inspector(moved))
    assert report == ["redis:8-alpine: recorded ONBUILD nothing, docker says ONBUILD VOLUME /x"]


def test_a_row_that_moved_in_both_dimensions_reports_both() -> None:
    """One line per dimension, since the two are separate readings of separate config fields."""
    moved = {**FAKE, "redis:8-alpine": Row(("/data",), ("VOLUME /x",))}
    assert len(rederive(FAKE, FAKE, _inspector(moved))) == 2


def test_a_row_written_in_another_order_is_the_same_row() -> None:
    """The comparison is over which paths an image declares, not over how the record lists them,
    so reordering a row is a tidiness question and never a drift report."""
    unsorted = {"dovecot/dovecot:2.3.21": Row(("/srv/mail", "/etc/dovecot"), ())}
    assert rederive(unsorted, unsorted, _inspector(FAKE)) == []


def test_triggers_written_in_another_order_are_another_image() -> None:
    """They fire in order, so unlike the paths they are held to what docker said, as written."""
    swapped = {"redis:8-alpine": Row((), ("RUN true", "VOLUME /x"))}
    answers = {"redis:8-alpine": Row((), ("VOLUME /x", "RUN true"))}
    assert len(rederive(swapped, swapped, _inspector(answers))) == 1


def test_an_image_the_record_has_no_row_for_is_reported() -> None:
    """The direction a new override arrives from: named by a compose file, recorded nowhere."""
    named = [*FAKE, "node:22-bookworm-slim"]
    answers = {**FAKE, "node:22-bookworm-slim": Row((), ())}
    report = rederive(named, FAKE, _inspector(answers))
    assert report == [
        "node:22-bookworm-slim: docker says nothing and ONBUILD nothing, and the record has no row"
    ]


def test_a_row_no_compose_file_names_is_still_asked_about() -> None:
    """The union is asked, not the names: a stale row that also drifted deserves both answers."""
    assert rederive([], FAKE, _inspector(FAKE)) == []


def test_an_image_docker_cannot_answer_about_is_reported_rather_than_skipped() -> None:
    """A rederivation quietly leaving a row unverified would confirm what it was run to doubt."""
    report = rederive(["gone:1"], {"gone:1": Row((), ())}, _inspector(FAKE))
    assert report == ["gone:1: docker image inspect failed: no such image: gone:1"]


def test_every_disagreement_is_reported_in_one_pass() -> None:
    """One drifted row must not hide the next; the report is the whole union, sorted."""
    report = rederive(["absent:1"], {"redis:8-alpine": Row(("/data",), ())}, _inspector(FAKE))
    assert len(report) == 2
    assert report[0].startswith("absent:1: docker image inspect failed")
    assert report[1] == "redis:8-alpine: recorded /data, docker says nothing"


# The rows compose builds rather than pulls, which are the ones no registry can refresh.
BUILT = ("cortex-brain", "cortex-mcp-email", "cortex-model-host")


# ── the real daemon ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_the_record_matches_a_real_docker() -> None:
    """What `just image-volumes` runs: every recorded row, asked of the daemon that measured it.

    Host-only by nature, so it is excluded from the coverage gate and never runs in CI. It needs
    a working network and a docker that can reach these registries, since every reference but the
    three built here is pulled before it is asked; those three need a local build, which one
    `just up-gpu` and one `just up-memory` leave behind.
    """
    assert rederive(IMAGE_VOLUMES, IMAGE_VOLUMES, docker_volumes, built=BUILT) == []


# ── asking the registry rather than the cache ──────────────────────────────────


def _recording(asked: dict[str, bool]) -> imagedrift.Inspector:
    """An inspector that records whether each reference was refreshed before it was asked."""

    def inspect(reference: str, *, pull: bool) -> Row:
        asked[reference] = pull
        return Row((), ())

    return inspect


def test_a_registry_image_is_refreshed_before_it_is_asked_about() -> None:
    """`docker image inspect` reads the local cache, so a re-derivation that skipped the pull

    would confirm a month-old copy of a moving tag under a name the registry has republished,
    which is the one drift this record exists to catch.
    """
    asked: dict[str, bool] = {}
    assert rederive(["redis:8-alpine"], {"redis:8-alpine": Row((), ())}, _recording(asked)) == []
    assert asked == {"redis:8-alpine": True}


def test_an_image_this_repo_builds_is_asked_about_without_a_pull() -> None:
    """There is no registry to refresh it from: the local build is the thing a container runs."""
    asked: dict[str, bool] = {}
    records = {"cortex-brain": Row((), ())}
    rederive(["cortex-brain"], records, _recording(asked), built=["cortex-brain"])
    assert asked == {"cortex-brain": False}


def test_a_row_naming_no_image_is_still_refreshed() -> None:
    """A stale row is asked about like any other, and nothing says the tag it names is local."""
    asked: dict[str, bool] = {}
    rederive([], {"gone:1": Row((), ())}, _recording(asked), built=["cortex-brain"])
    assert asked == {"gone:1": True}
