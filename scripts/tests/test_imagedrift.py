from collections.abc import Mapping

import pytest

import imagedrift
from imagedrift import InspectError, docker_volumes, parse, recompute, render
from imagevolumes import IMAGE_VOLUMES, Row

FAKE: dict[str, Row] = {
    "dovecot/dovecot:2.3.21": Row(("/etc/dovecot", "/srv/mail"), ()),
    "redis:8-alpine": Row((), ()),
}


def _inspector(answers: Mapping[str, Row]) -> imagedrift.Inspector:
    """Return an inspector that reads from a dict and raises on anything else, as docker does."""

    def inspect(reference: str, *, pull: bool) -> Row:  # noqa: ARG001
        try:
            return answers[reference]
        except KeyError as err:
            msg = f"docker image inspect failed: no such image: {reference}"
            raise InspectError(msg) from err

    return inspect


def test_an_image_declaring_both_kinds_is_read_into_both_dimensions() -> None:
    answered = '{"/srv/mail":{},"/etc/dovecot":{}}\n["VOLUME /probe/onbuild","RUN true"]'
    assert parse(answered) == Row(
        ("/etc/dovecot", "/srv/mail"), ("VOLUME /probe/onbuild", "RUN true")
    )


def test_an_image_declaring_neither_answers_null_in_both_lines() -> None:
    assert parse("null\nnull\n") == Row((), ())


def test_a_trigger_with_a_newline_stays_one_entry() -> None:
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
    with pytest.raises(InspectError, match=message):
        parse(answered)


def test_render_writes_an_empty_answer_in_words() -> None:
    assert (render(()), render(("/a", "/b"))) == ("nothing", "/a, /b")


def test_a_record_docker_still_agrees_with_reports_nothing() -> None:
    assert recompute(FAKE, FAKE, _inspector(FAKE)) == []


def test_a_row_docker_has_stopped_agreeing_with_is_reported_both_ways_round() -> None:
    moved = {**FAKE, "redis:8-alpine": Row(("/data",), ())}
    report = recompute(FAKE, FAKE, _inspector(moved))
    assert report == ["redis:8-alpine: recorded nothing, docker says /data"]


def test_a_base_that_has_gained_a_trigger_is_reported_as_the_dimension_it_moved_in() -> None:
    moved = {**FAKE, "redis:8-alpine": Row((), ("VOLUME /x",))}
    report = recompute(FAKE, FAKE, _inspector(moved))
    assert report == ["redis:8-alpine: recorded ONBUILD nothing, docker says ONBUILD VOLUME /x"]


def test_a_row_that_moved_in_both_dimensions_reports_both() -> None:
    moved = {**FAKE, "redis:8-alpine": Row(("/data",), ("VOLUME /x",))}
    assert len(recompute(FAKE, FAKE, _inspector(moved))) == 2


def test_a_row_written_in_another_order_is_the_same_row() -> None:
    unsorted = {"dovecot/dovecot:2.3.21": Row(("/srv/mail", "/etc/dovecot"), ())}
    assert recompute(unsorted, unsorted, _inspector(FAKE)) == []


def test_triggers_written_in_another_order_are_another_image() -> None:
    swapped = {"redis:8-alpine": Row((), ("RUN true", "VOLUME /x"))}
    answers = {"redis:8-alpine": Row((), ("VOLUME /x", "RUN true"))}
    assert len(recompute(swapped, swapped, _inspector(answers))) == 1


def test_an_image_the_record_has_no_row_for_is_reported() -> None:
    named = [*FAKE, "node:22-bookworm-slim"]
    answers = {**FAKE, "node:22-bookworm-slim": Row((), ())}
    report = recompute(named, FAKE, _inspector(answers))
    assert report == [
        "node:22-bookworm-slim: docker says nothing and ONBUILD nothing, and the record has no row"
    ]


def test_a_row_no_compose_file_names_is_still_asked_about() -> None:
    assert recompute([], FAKE, _inspector(FAKE)) == []


def test_an_image_docker_cannot_answer_about_is_reported_rather_than_skipped() -> None:
    report = recompute(["gone:1"], {"gone:1": Row((), ())}, _inspector(FAKE))
    assert report == ["gone:1: docker image inspect failed: no such image: gone:1"]


def test_every_disagreement_is_reported_in_one_pass() -> None:
    report = recompute(["absent:1"], {"redis:8-alpine": Row(("/data",), ())}, _inspector(FAKE))
    assert len(report) == 2
    assert report[0].startswith("absent:1: docker image inspect failed")
    assert report[1] == "redis:8-alpine: recorded /data, docker says nothing"


BUILT = ("cortex-brain", "cortex-mcp-email", "cortex-model-host")


@pytest.mark.integration
def test_the_record_matches_a_real_docker() -> None:
    assert recompute(IMAGE_VOLUMES, IMAGE_VOLUMES, docker_volumes, built=BUILT) == []


def _recording(asked: dict[str, bool]) -> imagedrift.Inspector:
    """Return an inspector that records whether each reference was pulled before it was read."""

    def inspect(reference: str, *, pull: bool) -> Row:
        asked[reference] = pull
        return Row((), ())

    return inspect


def test_a_registry_image_is_refreshed_before_it_is_asked_about() -> None:
    asked: dict[str, bool] = {}
    assert recompute(["redis:8-alpine"], {"redis:8-alpine": Row((), ())}, _recording(asked)) == []
    assert asked == {"redis:8-alpine": True}


def test_an_image_this_repo_builds_is_asked_about_without_a_pull() -> None:
    asked: dict[str, bool] = {}
    records = {"cortex-brain": Row((), ())}
    recompute(["cortex-brain"], records, _recording(asked), built=["cortex-brain"])
    assert asked == {"cortex-brain": False}


def test_a_row_naming_no_image_is_still_refreshed() -> None:
    asked: dict[str, bool] = {}
    recompute([], {"gone:1": Row((), ())}, _recording(asked), built=["cortex-brain"])
    assert asked == {"gone:1": True}
