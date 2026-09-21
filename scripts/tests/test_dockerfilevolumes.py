from pathlib import Path

import pytest

from composeservices import DEFAULT_DOCKERFILE, Build
from dockerfilebases import DockerfileError
from dockerfilevolumes import landings, onbuild_volumes, read_volumes, undeclared
from imagevolumes import Row

REPO_ROOT = Path(__file__).resolve().parents[2]

HERE = Build(".", DEFAULT_DOCKERFILE)


def _tree(root: Path, dockerfile: str) -> Path:
    """Write a test tree whose compose file sits beside the Dockerfile it builds from."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    (root / DEFAULT_DOCKERFILE).write_text(dockerfile, encoding="utf-8")
    return root / "docker" / "docker-compose.yml"


def test_a_plain_volume_declares_the_path_it_names() -> None:
    assert read_volumes("FROM scratch\nVOLUME /srv/mail\n") == ("/srv/mail",)


def test_a_plain_volume_may_name_several_paths_on_one_line() -> None:
    assert read_volumes("VOLUME /a /b\n") == ("/a", "/b")


def test_a_json_array_volume_declares_every_path_in_it() -> None:
    assert read_volumes('VOLUME ["/a", "/b"]\n') == ("/a", "/b")


def test_the_instruction_is_matched_however_it_is_cased() -> None:
    assert read_volumes("volume /a\n") == ("/a",)


def test_a_declaration_split_across_a_continuation_is_read_whole() -> None:
    assert read_volumes("VOLUME \\\n  /a \\\n  /b\n") == ("/a", "/b")


def test_a_comment_between_continued_lines_is_dropped_the_way_docker_drops_it() -> None:
    assert read_volumes("VOLUME \\\n# a note\n  /a\n") == ("/a",)


def test_a_trailing_slash_is_not_a_second_spelling_of_one_path() -> None:
    assert read_volumes("VOLUME /srv/mail/\n") == ("/srv/mail",)


def test_a_file_declaring_nothing_declares_nothing() -> None:
    assert read_volumes('FROM scratch\n# VOLUME /a\n\nCMD ["true"]\n') == ()


def test_an_onbuild_volume_is_not_this_image_declaring_one() -> None:
    assert read_volumes("ONBUILD VOLUME /a\n") == ()


def test_an_instruction_left_open_on_a_continuation_is_still_read() -> None:
    assert read_volumes("VOLUME \\\n  /a \\\n") == ("/a",)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("VOLUME ${CACHE}\n", "carries an expansion"),
        ("VOLUME\n", "names no path"),
        ("VOLUME []\n", "names no path"),
        ("VOLUME relative/path\n", "is not an absolute container path"),
        ('VOLUME ["/a"\n', "is not a JSON array:"),
        ('VOLUME ["/a", 7]\n', "which is not a path"),
        ("VOLUME [1, 2]\n", "which is not a path"),
        ("# escape=`\nVOLUME /a\n", "escape directive"),
    ],
)
def test_a_shape_the_reader_was_not_taught_is_refused(text: str, message: str) -> None:
    with pytest.raises(DockerfileError, match=message):
        read_volumes(text)


def test_a_json_scalar_is_refused_as_an_array_rather_than_read_as_a_path() -> None:
    with pytest.raises(DockerfileError, match="is not a JSON array"):
        read_volumes('VOLUME ["/a"] extra\n')


def test_a_json_object_is_refused_for_the_reason_it_is_wrong() -> None:
    with pytest.raises(DockerfileError, match="is not a JSON array"):
        read_volumes('VOLUME {"a": 1}\n')


def test_an_escape_directive_below_the_first_instruction_is_an_ordinary_comment() -> None:
    assert read_volumes("FROM scratch\n# escape=`\nVOLUME /a\n") == ("/a",)


def test_a_recorded_trigger_declares_the_path_it_names() -> None:
    assert onbuild_volumes(("VOLUME /probe/onbuild",)) == ("/probe/onbuild",)


def test_a_trigger_is_read_in_both_spellings_and_however_it_is_cased() -> None:
    assert onbuild_volumes(('volume ["/a", "/b"]', "VOLUME /c")) == ("/a", "/b", "/c")


def test_a_trigger_that_is_not_a_volume_declares_nothing() -> None:
    assert onbuild_volumes(("RUN true", "COPY . /app")) == ()


def test_an_image_carrying_no_trigger_declares_nothing_through_one() -> None:
    assert onbuild_volumes(()) == ()


@pytest.mark.parametrize("entry", ["/probe/onbuild", ""], ids=["path", "empty"])
def test_a_trigger_not_opening_with_an_instruction_is_refused(entry: str) -> None:
    with pytest.raises(DockerfileError, match="does not open with an instruction"):
        onbuild_volumes((entry,))


def test_a_trigger_the_reader_cannot_read_is_refused_rather_than_resolved_to_nothing() -> None:
    with pytest.raises(DockerfileError, match="carries an expansion"):
        onbuild_volumes(("VOLUME ${CACHE}",))


def test_a_context_is_resolved_against_the_repo_root(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    assert landings(tmp_path, compose, HERE) == [tmp_path / DEFAULT_DOCKERFILE]


def test_a_context_is_resolved_against_the_compose_files_own_directory_too(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    (tmp_path / "docker" / DEFAULT_DOCKERFILE).write_text("FROM scratch\n", encoding="utf-8")
    assert landings(tmp_path, compose, HERE) == [
        tmp_path / DEFAULT_DOCKERFILE,
        tmp_path / "docker" / DEFAULT_DOCKERFILE,
    ]


def test_a_compose_file_at_the_root_has_only_one_project_directory(tmp_path: Path) -> None:
    (tmp_path / DEFAULT_DOCKERFILE).write_text("FROM scratch\n", encoding="utf-8")
    compose = tmp_path / "compose.yml"
    assert landings(tmp_path, compose, HERE) == [tmp_path / DEFAULT_DOCKERFILE]


def test_an_absolute_context_lands_on_one_file_rather_than_twice(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    absolute = Build(tmp_path.as_posix(), DEFAULT_DOCKERFILE)
    assert landings(tmp_path, compose, absolute) == [tmp_path / DEFAULT_DOCKERFILE]


def test_a_declared_path_the_row_does_not_carry_is_reported(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\nVOLUME /var/cache/thing\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.dockerfiles == (DEFAULT_DOCKERFILE,)
    assert len(reading.faults) == 1
    assert "declares VOLUME '/var/cache/thing'" in reading.faults[0]
    assert "'tree-brain'" in reading.faults[0]


def test_a_declared_path_the_row_carries_is_the_record_in_step(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\nVOLUME /var/cache/thing\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", ("/var/cache/thing",), {})
    assert reading == ((DEFAULT_DOCKERFILE,), (), (), ())


def test_a_recorded_path_neither_the_file_nor_its_base_declares_is_not_a_fault(
    tmp_path: Path,
) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ())}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", ("/inherited",), records)
    assert reading == ((DEFAULT_DOCKERFILE,), ("base:1",), (), ())


def test_a_path_the_base_declares_and_the_row_lacks_is_reported(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row(("/inherited",), ())}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), records)
    assert reading.bases == ("base:1",)
    assert len(reading.faults) == 1
    assert "FROM 'base:1', which declares VOLUME '/inherited'" in reading.faults[0]


def test_a_path_the_base_declares_and_the_row_carries_is_the_record_in_step(
    tmp_path: Path,
) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row(("/inherited",), ())}
    assert undeclared(tmp_path, compose, HERE, "tree-brain", ("/inherited/",), records) == (
        (DEFAULT_DOCKERFILE,),
        ("base:1",),
        (),
        (),
    )


def test_a_path_a_bases_trigger_would_declare_and_the_row_lacks_is_reported(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ("VOLUME /triggered",))}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), records)
    assert reading.bases == ("base:1",)
    assert len(reading.faults) == 1
    assert "whose ONBUILD declares VOLUME '/triggered'" in reading.faults[0]
    assert "'tree-brain'" in reading.faults[0]


def test_a_path_a_bases_trigger_declares_and_the_row_carries_is_the_record_in_step(
    tmp_path: Path,
) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ("VOLUME /triggered/",))}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", ("/triggered",), records)
    assert reading == ((DEFAULT_DOCKERFILE,), ("base:1",), (), ())


def test_a_recorded_trigger_the_reader_refuses_is_unasked_on_the_build_that_stands_on_it(
    tmp_path: Path,
) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ("VOLUME relative/path",))}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), records)
    assert reading.faults == ()
    assert len(reading.unasked) == 1
    assert "whose recorded ONBUILD this reader will not guess at" in reading.unasked[0]
    assert "is not an absolute container path" in reading.unasked[0]


def test_a_base_with_no_row_owes_no_trigger_fault_on_top_of_the_unrecorded_one(
    tmp_path: Path,
) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert len(reading.faults) == 1


def test_a_file_standing_on_nothing_is_asked_about_no_trigger(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    records = {"base:1": Row((), ("VOLUME /triggered",))}
    assert undeclared(tmp_path, compose, HERE, "tree-brain", (), records).faults == ()


def test_a_base_the_record_has_no_row_for_is_a_fault(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM base:1\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.bases == ("base:1",)
    assert len(reading.faults) == 1
    assert "has no row for" in reading.faults[0]


def test_a_file_standing_on_nothing_asks_for_no_base_row(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    assert undeclared(tmp_path, compose, HERE, "tree-brain", (), {}).bases == ()


def test_a_row_carrying_a_trailing_slash_still_covers_the_path(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\nVOLUME /srv/mail\n")
    assert undeclared(tmp_path, compose, HERE, "tree-brain", ("/srv/mail/",), {}).faults == ()


def test_a_build_pointing_where_no_dockerfile_lands_is_unasked(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    reading = undeclared(tmp_path, compose, Build("./nowhere", "Dockerfile"), "tree-x", (), {})
    assert reading.faults == ()
    assert len(reading.unasked) == 1
    assert "where no Dockerfile lands" in reading.unasked[0]


@pytest.mark.parametrize(
    "build",
    [Build("${DIR:-./brain}", DEFAULT_DOCKERFILE), Build(".", "${FILE}")],
    ids=["context", "dockerfile"],
)
def test_a_build_path_spelled_through_a_substitution_is_unasked(
    tmp_path: Path, build: Build
) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    reading = undeclared(tmp_path, compose, build, "tree-brain", (), {})
    assert reading.faults == ()
    assert len(reading.unasked) == 1
    assert "carries a substitution" in reading.unasked[0]


def test_a_dockerfile_the_reader_refuses_is_unasked_rather_than_a_silence(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "VOLUME ${CACHE}\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.dockerfiles == (DEFAULT_DOCKERFILE,)
    assert reading.faults == ()
    assert len(reading.unasked) == 1
    assert "could not be read" in reading.unasked[0]
    assert "carries an expansion" in reading.unasked[0]


def test_a_dockerfile_that_is_not_text_is_unasked(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    (tmp_path / DEFAULT_DOCKERFILE).write_bytes(b"\xff\xfe VOLUME")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.faults == ()
    assert len(reading.unasked) == 1
    assert "could not be read" in reading.unasked[0]


def test_a_dockerfile_outside_the_root_is_named_by_the_way_back_to_it(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    compose = _tree(root, "FROM scratch\nVOLUME /a\n")
    outside = Build("..", DEFAULT_DOCKERFILE)
    (tmp_path / DEFAULT_DOCKERFILE).write_text("FROM scratch\nVOLUME /outside\n", encoding="utf-8")
    reading = undeclared(root, compose, outside, "tree-brain", (), {})
    assert reading.dockerfiles == ("../Dockerfile", DEFAULT_DOCKERFILE)
    assert "'/outside'" in reading.faults[0]
    assert "'/a'" in reading.faults[1]


def test_this_repos_own_dockerfiles_are_readable_and_declare_nothing() -> None:
    built = ["brain/Dockerfile", "brain/Dockerfile.modelhost"]
    read = {name: (REPO_ROOT / name).read_text(encoding="utf-8") for name in built}
    assert {name: read_volumes(text) for name, text in read.items()} == dict.fromkeys(built, ())
    assert all("FROM" in text for text in read.values()), read
