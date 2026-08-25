"""Behaviour of the recorded image-volume table and of the rederivation that keeps it honest."""

from collections.abc import Mapping

import pytest

import imagevolumes
from imagevolumes import IMAGE_VOLUMES, InspectError, docker_volumes, rederive, render

FAKE: dict[str, tuple[str, ...]] = {
    "dovecot/dovecot:2.3.21": ("/etc/dovecot", "/srv/mail"),
    "redis:8-alpine": (),
}


def _inspector(answers: Mapping[str, tuple[str, ...]]) -> imagevolumes.Inspector:
    """An inspector answering from a dict and refusing anything else, the way docker does."""

    def inspect(reference: str) -> tuple[str, ...]:
        try:
            return answers[reference]
        except KeyError as err:
            msg = f"docker image inspect failed: no such image: {reference}"
            raise InspectError(msg) from err

    return inspect


# ── the record itself ──────────────────────────────────────────────────────────


def test_every_recorded_path_is_an_absolute_container_path() -> None:
    """A relative row could never match a mount target, so the gate would read it as a leak."""
    assert all(path.startswith("/") for paths in IMAGE_VOLUMES.values() for path in paths)


def test_the_record_holds_the_images_that_declare_nothing_too() -> None:
    """A measured silence is what tells an image nobody has asked about from one that answered."""
    silent = [reference for reference, paths in IMAGE_VOLUMES.items() if not paths]
    assert len(silent) >= 2, IMAGE_VOLUMES
    assert len(silent) < len(IMAGE_VOLUMES), IMAGE_VOLUMES


def test_each_rows_paths_are_written_in_the_order_docker_sorts_them() -> None:
    """A tidiness the comparison does not need and a reader does: one row, one obvious order."""
    assert all(list(paths) == sorted(paths) for paths in IMAGE_VOLUMES.values())


# ── how a report reads ─────────────────────────────────────────────────────────


def test_render_spells_an_empty_answer_in_words() -> None:
    assert (render(()), render(("/a", "/b"))) == ("nothing", "/a, /b")


# ── rederivation ───────────────────────────────────────────────────────────────


def test_a_record_docker_still_agrees_with_reports_nothing() -> None:
    assert rederive(FAKE, FAKE, _inspector(FAKE)) == []


def test_a_row_docker_has_stopped_agreeing_with_is_reported_both_ways_round() -> None:
    """The message carries both answers, because the fix is to edit one of them into the other."""
    moved = {**FAKE, "redis:8-alpine": ("/data",)}
    report = rederive(FAKE, FAKE, _inspector(moved))
    assert report == ["redis:8-alpine: recorded nothing, docker says /data"]


def test_a_row_written_in_another_order_is_the_same_row() -> None:
    """The comparison is over which paths an image declares, not over how the record lists them,
    so reordering a row is a tidiness question and never a drift report."""
    unsorted = {"dovecot/dovecot:2.3.21": ("/srv/mail", "/etc/dovecot")}
    assert rederive(unsorted, unsorted, _inspector(FAKE)) == []


def test_an_image_the_record_has_no_row_for_is_reported() -> None:
    """The direction a new override arrives from: named by a compose file, recorded nowhere."""
    named = [*FAKE, "node:22-bookworm-slim"]
    answers = {**FAKE, "node:22-bookworm-slim": ()}
    report = rederive(named, FAKE, _inspector(answers))
    assert report == ["node:22-bookworm-slim: docker says nothing, and the record has no row"]


def test_a_row_no_compose_file_names_is_still_asked_about() -> None:
    """The union is asked, not the names: a stale row that also drifted deserves both answers."""
    assert rederive([], FAKE, _inspector(FAKE)) == []


def test_an_image_docker_cannot_answer_about_is_reported_rather_than_skipped() -> None:
    """A rederivation quietly leaving a row unverified would confirm what it was run to doubt."""
    report = rederive(["gone:1"], {"gone:1": ()}, _inspector(FAKE))
    assert report == ["gone:1: docker image inspect failed: no such image: gone:1"]


def test_every_disagreement_is_reported_in_one_pass() -> None:
    """One drifted row must not hide the next; the report is the whole union, sorted."""
    report = rederive(["absent:1"], {"redis:8-alpine": ("/data",)}, _inspector(FAKE))
    assert len(report) == 2
    assert report[0].startswith("absent:1: docker image inspect failed")
    assert report[1] == "redis:8-alpine: recorded /data, docker says nothing"


# ── the real daemon ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_the_record_matches_a_real_docker() -> None:
    """What `just image-volumes` runs: every recorded row, asked of the daemon that measured it."""
    assert rederive(IMAGE_VOLUMES, IMAGE_VOLUMES, docker_volumes) == []
