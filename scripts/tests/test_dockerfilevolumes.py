"""Tests for the Dockerfile side of the image-volume record: what a file here declares.

Two kinds of thing are exercised, and they fail in different directions. `read_volumes` and
`onbuild_volumes` are readers, so most of what is below asserts a raise: a shape one was not
taught raises rather than being walked past, since a `VOLUME` this reader skipped is a declared
path the record would go on denying. `undeclared` is the rule over them, and it is where every
side of a built row meets: what the file declares itself, what its base declares for it, and what
its base's triggers would declare into it, asked over one read. All are one-directional by design,
so the tests that matter most are the ones asserting what is *not* a fault: a path the row already
carries, and a row carrying a path no side ever names.
"""

from pathlib import Path

import pytest

from composeservices import DEFAULT_DOCKERFILE, Build
from dockerfilebases import DockerfileError
from dockerfilevolumes import landings, onbuild_volumes, read_volumes, undeclared
from imagevolumes import Row

REPO_ROOT = Path(__file__).resolve().parents[2]

HERE = Build(".", DEFAULT_DOCKERFILE)


def _tree(root: Path, dockerfile: str) -> Path:
    """Write a fixture tree whose compose file sits beside the Dockerfile it builds from."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    (root / DEFAULT_DOCKERFILE).write_text(dockerfile, encoding="utf-8")
    return root / "docker" / "docker-compose.yml"


# ── reading one Dockerfile ─────────────────────────────────────────────────────


def test_a_plain_volume_declares_the_path_it_names() -> None:
    assert read_volumes("FROM scratch\nVOLUME /srv/mail\n") == ("/srv/mail",)


def test_a_plain_volume_may_name_several_paths_on_one_line() -> None:
    assert read_volumes("VOLUME /a /b\n") == ("/a", "/b")


def test_a_json_array_volume_declares_every_path_in_it() -> None:
    assert read_volumes('VOLUME ["/a", "/b"]\n') == ("/a", "/b")


def test_the_instruction_is_matched_however_it_is_cased() -> None:
    """Docker matches the instruction case-insensitively, so a case-sensitive reader would miss a
    real declaration."""
    assert read_volumes("volume /a\n") == ("/a",)


def test_a_declaration_split_across_a_continuation_is_read_whole() -> None:
    assert read_volumes("VOLUME \\\n  /a \\\n  /b\n") == ("/a", "/b")


def test_a_comment_between_continued_lines_is_dropped_the_way_docker_drops_it() -> None:
    assert read_volumes("VOLUME \\\n# a note\n  /a\n") == ("/a",)


def test_a_trailing_slash_is_not_a_second_spelling_of_one_path() -> None:
    assert read_volumes("VOLUME /srv/mail/\n") == ("/srv/mail",)


def test_a_file_declaring_nothing_declares_nothing() -> None:
    """Both of this repo's Dockerfiles give this answer, and it is an answer rather than a skipped
    read."""
    assert read_volumes('FROM scratch\n# VOLUME /a\n\nCMD ["true"]\n') == ()


def test_an_onbuild_volume_is_not_this_image_declaring_one() -> None:
    """It declares a volume in an image built from this one, which is a different image's row."""
    assert read_volumes("ONBUILD VOLUME /a\n") == ()


def test_an_instruction_left_open_on_a_continuation_is_still_read() -> None:
    """A file ending mid-continuation is malformed, and the paths read so far are reported rather
    than none of them."""
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
    """A skipped VOLUME is a declared path the record would go on denying, so none is skipped."""
    with pytest.raises(DockerfileError, match=message):
        read_volumes(text)


def test_a_json_scalar_is_refused_as_an_array_rather_than_read_as_a_path() -> None:
    with pytest.raises(DockerfileError, match="is not a JSON array"):
        read_volumes('VOLUME ["/a"] extra\n')


def test_a_json_object_is_refused_for_the_reason_it_is_wrong() -> None:
    """A JSON object parses, so the fault names the array it is not rather than a path that failed
    to be absolute."""
    with pytest.raises(DockerfileError, match="is not a JSON array"):
        read_volumes('VOLUME {"a": 1}\n')


def test_an_escape_directive_below_the_first_instruction_is_an_ordinary_comment() -> None:
    """Parser directives sit at the top of a file; a line below one is a comment about escaping."""
    assert read_volumes("FROM scratch\n# escape=`\nVOLUME /a\n") == ("/a",)


# ── reading a base's recorded triggers ─────────────────────────────────────────


def test_a_recorded_trigger_declares_the_path_it_names() -> None:
    """The dimension is recorded as docker wrote it, and the paths are read here, by the gate
    everybody runs rather than once on one machine."""
    assert onbuild_volumes(("VOLUME /probe/onbuild",)) == ("/probe/onbuild",)


def test_a_trigger_is_read_in_both_spellings_and_however_it_is_cased() -> None:
    """Docker writes the instruction down as the file wrote it, lower case and array alike."""
    assert onbuild_volumes(('volume ["/a", "/b"]', "VOLUME /c")) == ("/a", "/b", "/c")


def test_a_trigger_that_is_not_a_volume_declares_nothing() -> None:
    """A base may carry any instruction as a trigger, and only one of them makes a volume."""
    assert onbuild_volumes(("RUN true", "COPY . /app")) == ()


def test_an_image_carrying_no_trigger_declares_nothing_through_one() -> None:
    """Every row in this repo's record gives this answer today, and it is an answer rather than a
    gap."""
    assert onbuild_volumes(()) == ()


@pytest.mark.parametrize("entry", ["/probe/onbuild", ""], ids=["path", "empty"])
def test_a_trigger_not_opening_with_an_instruction_is_refused(entry: str) -> None:
    """This one is aimed at whoever pastes a row rather than at docker: a trigger written as the
    path it resolves to would read as an instruction this reader passes over, and the row would
    then declare nothing while the base declares a path."""
    with pytest.raises(DockerfileError, match="does not open with an instruction"):
        onbuild_volumes((entry,))


def test_a_trigger_the_reader_cannot_read_is_refused_rather_than_resolved_to_nothing() -> None:
    """It is a path the next build may declare, so reading it as nothing would leave the gate
    agreeing with a record that denies it."""
    with pytest.raises(DockerfileError, match="carries an expansion"):
        onbuild_volumes(("VOLUME ${CACHE}",))


# ── finding the file a service builds from ─────────────────────────────────────


def test_a_context_is_resolved_against_the_repo_root(tmp_path: Path) -> None:
    """What the `just` recipes pass, and where every build stanza in this tree resolves."""
    compose = _tree(tmp_path, "FROM scratch\n")
    assert landings(tmp_path, compose, HERE) == [tmp_path / DEFAULT_DOCKERFILE]


def test_a_context_is_resolved_against_the_compose_files_own_directory_too(tmp_path: Path) -> None:
    """A bare `docker compose -f docker/...` takes the project directory from the file itself."""
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
    """Both project directories resolve an absolute context to the same file, and one file read
    twice would report the same declaration twice."""
    compose = _tree(tmp_path, "FROM scratch\n")
    absolute = Build(tmp_path.as_posix(), DEFAULT_DOCKERFILE)
    assert landings(tmp_path, compose, absolute) == [tmp_path / DEFAULT_DOCKERFILE]


# ── the rule over it ───────────────────────────────────────────────────────────


def test_a_declared_path_the_row_does_not_carry_is_reported(tmp_path: Path) -> None:
    """This is the case the rule exists for: the built image declares a path and the record goes on
    denying it."""
    compose = _tree(tmp_path, "FROM scratch\nVOLUME /var/cache/thing\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.dockerfiles == (DEFAULT_DOCKERFILE,)
    assert len(reading.faults) == 1
    assert "declares VOLUME '/var/cache/thing'" in reading.faults[0]
    assert "'tree-brain'" in reading.faults[0]


def test_a_declared_path_the_row_carries_is_the_record_in_step(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\nVOLUME /var/cache/thing\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", ("/var/cache/thing",), {})
    assert reading == ((DEFAULT_DOCKERFILE,), (), ())


def test_a_recorded_path_neither_the_file_nor_its_base_declares_is_not_a_fault(
    tmp_path: Path,
) -> None:
    """Both rules are one-directional, so a row carrying more than the two sides declare is not a
    drift: what is declared is held to what is recorded, and never the reverse."""
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ())}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", ("/inherited",), records)
    assert reading == ((DEFAULT_DOCKERFILE,), ("base:1",), ())


def test_a_path_the_base_declares_and_the_row_lacks_is_reported(tmp_path: Path) -> None:
    """The half a built row cannot catch itself: the base was republished with a declaration, and
    the row goes on answering from whatever the machine running the recipe last built."""
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row(("/inherited",), ())}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), records)
    assert reading.bases == ("base:1",)
    assert len(reading.faults) == 1
    assert "FROM 'base:1', which declares VOLUME '/inherited'" in reading.faults[0]


def test_a_path_the_base_declares_and_the_row_carries_is_the_record_in_step(
    tmp_path: Path,
) -> None:
    """And the two sides are compared as paths, so one trailing slash is not a second spelling."""
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row(("/inherited",), ())}
    assert undeclared(tmp_path, compose, HERE, "tree-brain", ("/inherited/",), records) == (
        (DEFAULT_DOCKERFILE,),
        ("base:1",),
        (),
    )


def test_a_path_a_bases_trigger_would_declare_and_the_row_lacks_is_reported(tmp_path: Path) -> None:
    """The gap the trigger dimension closes: the base declares nothing of its own, the next build
    from it declares the path anyway, and every row the two other sides read says nothing."""
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
    """The rule is one-directional here too, and the two sides are compared as paths."""
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ("VOLUME /triggered/",))}
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", ("/triggered",), records)
    assert reading == ((DEFAULT_DOCKERFILE,), ("base:1",), ())


def test_a_recorded_trigger_the_reader_refuses_is_a_fault_on_the_build_that_stands_on_it(
    tmp_path: Path,
) -> None:
    """A row nobody can read is not the same as a base declaring nothing, so the fault names the
    file, the row and what could not be read, the fix being a hand edit at the record."""
    compose = _tree(tmp_path, "FROM base:1\n")
    records = {"base:1": Row((), ("VOLUME relative/path",))}
    faults = undeclared(tmp_path, compose, HERE, "tree-brain", (), records).faults
    assert len(faults) == 1
    assert "whose recorded ONBUILD this reader will not guess at" in faults[0]
    assert "is not an absolute container path" in faults[0]


def test_a_base_with_no_row_owes_no_trigger_fault_on_top_of_the_unrecorded_one(
    tmp_path: Path,
) -> None:
    """There is nothing to read, and the unrecorded base already says what to do about it."""
    compose = _tree(tmp_path, "FROM base:1\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert len(reading.faults) == 1


def test_a_file_standing_on_nothing_is_asked_about_no_trigger(tmp_path: Path) -> None:
    """`FROM scratch` names no base, so there is no row whose triggers could fire into this one."""
    compose = _tree(tmp_path, "FROM scratch\n")
    records = {"base:1": Row((), ("VOLUME /triggered",))}
    assert undeclared(tmp_path, compose, HERE, "tree-brain", (), records).faults == ()


def test_a_base_the_record_has_no_row_for_is_a_fault(tmp_path: Path) -> None:
    """An unrecorded base is an unasked question, exactly as an unrecorded image is one."""
    compose = _tree(tmp_path, "FROM base:1\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.bases == ("base:1",)
    assert len(reading.faults) == 1
    assert "has no row for" in reading.faults[0]


def test_a_file_standing_on_nothing_asks_for_no_base_row(tmp_path: Path) -> None:
    """`FROM scratch` inherits nothing, so the walk names no base and the record owes none."""
    compose = _tree(tmp_path, "FROM scratch\n")
    assert undeclared(tmp_path, compose, HERE, "tree-brain", (), {}).bases == ()


def test_a_row_carrying_a_trailing_slash_still_covers_the_path(tmp_path: Path) -> None:
    """One container path has one spelling on both sides of the comparison."""
    compose = _tree(tmp_path, "FROM scratch\nVOLUME /srv/mail\n")
    assert undeclared(tmp_path, compose, HERE, "tree-brain", ("/srv/mail/",), {}).faults == ()


def test_a_build_pointing_where_no_dockerfile_lands_is_a_fault(tmp_path: Path) -> None:
    """A build mapping that reaches no file checks nothing, so it is reported rather than passing
    over."""
    compose = _tree(tmp_path, "FROM scratch\n")
    faults = undeclared(
        tmp_path, compose, Build("./nowhere", "Dockerfile"), "tree-x", (), {}
    ).faults
    assert len(faults) == 1
    assert "where no Dockerfile lands" in faults[0]


@pytest.mark.parametrize(
    "build",
    [Build("${DIR:-./brain}", DEFAULT_DOCKERFILE), Build(".", "${FILE}")],
    ids=["context", "dockerfile"],
)
def test_a_build_path_spelled_through_a_substitution_is_a_fault(
    tmp_path: Path, build: Build
) -> None:
    """Only a build resolves it, so the file that declares the paths cannot be read at all."""
    compose = _tree(tmp_path, "FROM scratch\n")
    faults = undeclared(tmp_path, compose, build, "tree-brain", (), {}).faults
    assert len(faults) == 1
    assert "carries a substitution" in faults[0]


def test_a_dockerfile_the_reader_refuses_is_a_fault_rather_than_a_silence(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "VOLUME ${CACHE}\n")
    reading = undeclared(tmp_path, compose, HERE, "tree-brain", (), {})
    assert reading.dockerfiles == (DEFAULT_DOCKERFILE,)
    assert len(reading.faults) == 1
    assert "could not be read" in reading.faults[0]
    assert "carries an expansion" in reading.faults[0]


def test_a_dockerfile_that_is_not_text_is_a_fault(tmp_path: Path) -> None:
    compose = _tree(tmp_path, "FROM scratch\n")
    (tmp_path / DEFAULT_DOCKERFILE).write_bytes(b"\xff\xfe VOLUME")
    faults = undeclared(tmp_path, compose, HERE, "tree-brain", (), {}).faults
    assert len(faults) == 1
    assert "could not be read" in faults[0]


def test_a_dockerfile_outside_the_root_is_named_by_the_way_back_to_it(tmp_path: Path) -> None:
    """A context can point out of the tree, and a fault has to name the file it really read."""
    root = tmp_path / "repo"
    compose = _tree(root, "FROM scratch\nVOLUME /a\n")
    outside = Build("..", DEFAULT_DOCKERFILE)
    (tmp_path / DEFAULT_DOCKERFILE).write_text("FROM scratch\nVOLUME /outside\n", encoding="utf-8")
    reading = undeclared(root, compose, outside, "tree-brain", (), {})
    assert reading.dockerfiles == ("../Dockerfile", DEFAULT_DOCKERFILE)
    assert "'/outside'" in reading.faults[0]
    assert "'/a'" in reading.faults[1]


# ── the tree this reader is pointed at ─────────────────────────────────────────


def test_this_repos_own_dockerfiles_are_readable_and_declare_nothing() -> None:
    """This guards every fixture above: the shapes they exercise have to be the tree's shapes, and
    the empty answer here is measured rather than the result of a file nobody could parse."""
    built = ["brain/Dockerfile", "brain/Dockerfile.modelhost"]
    read = {name: (REPO_ROOT / name).read_text(encoding="utf-8") for name in built}
    assert {name: read_volumes(text) for name, text in read.items()} == dict.fromkeys(built, ())
    assert all("FROM" in text for text in read.values()), read
