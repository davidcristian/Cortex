"""Behaviour of the image-volume gate, over compose trees written for each verdict.

The rule has one shape and three ways of failing closed around it, and every one of them is
exercised here against a fake record rather than the repo's own, so a test says what it means
instead of depending on which images the tree happens to name today. The real record and the real
tree meet at the end, in the two tests that assert this repo is clean and that it gave the gate
something to be clean about.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

import volumecheck
from imagevolumes import IMAGE_VOLUMES, InspectError, Inspector

REPO_ROOT = Path(__file__).resolve().parents[2]

# A fake record: one image declaring a path, one measured silent, one built here by compose.
RECORDS: dict[str, tuple[str, ...]] = {"cache:1": (), "db:1": ("/var/lib/db",), "tree-brain": ()}

BASE = "name: tree\nservices:\n  brain:\n    build: ./brain\n"


def _write(root: Path, name: str, text: str) -> Path:
    """Put one compose file in the fixture tree, making the directory it lives in if need be."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _service(body: str, name: str = "db") -> str:
    """One override file declaring one service, indented into place."""
    return f"services:\n  {name}:\n{body}"


def _answering(answers: Mapping[str, tuple[str, ...]]) -> Inspector:
    """An inspector answering from a dict and refusing anything else, the way docker does."""

    def inspect(reference: str, *, pull: bool) -> tuple[str, ...]:  # noqa: ARG001
        try:
            return answers[reference]
        except KeyError as err:
            msg = f"docker image inspect failed: no such image: {reference}"
            raise InspectError(msg) from err

    return inspect


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A tree holding the base file, which pins the project every override inherits, beside the
    Dockerfile its one build stanza points at: a build reaching no file is a fault of its own."""
    _write(tmp_path, "docker/docker-compose.yml", BASE)
    _write(tmp_path, "brain/Dockerfile", "FROM scratch\n")
    return tmp_path


def _faults(tree: Path) -> list[volumecheck.Fault]:
    """Every fault about the tree itself, which is all of them but the stale rows.

    A fixture naming one image of the three leaves the other two rows unnamed, and that is the
    stale-row rule working rather than the file under test failing, so those are read separately
    by the one test that is about them.
    """
    return [
        fault
        for fault in volumecheck.check(tree, RECORDS).faults
        if fault.path != volumecheck.RECORD_PATH
    ]


# ── the rule ───────────────────────────────────────────────────────────────────


def test_a_declared_volume_the_service_mounts_nothing_at_is_reported(tree: Path) -> None:
    """The whole point: docker makes an anonymous volume there and `down` leaves it behind."""
    _write(tree, "docker/docker-compose.db.yml", _service("    image: db:1\n"))
    faults = _faults(tree)
    assert len(faults) == 1
    assert (faults[0].path, faults[0].line) == ("docker/docker-compose.db.yml", 2)
    assert "declares VOLUME '/var/lib/db'" in faults[0].detail


def test_a_declaration_covered_by_a_named_volume_is_accounted_for(tree: Path) -> None:
    body = "    image: db:1\n    volumes:\n      - db-data:/var/lib/db\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body))
    assert _faults(tree) == []


def test_a_declaration_covered_by_a_tmpfs_is_accounted_for(tree: Path) -> None:
    """How a container that writes nothing worth keeping answers the declaration."""
    body = "    image: db:1\n    tmpfs:\n      - /var/lib/db\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body))
    assert _faults(tree) == []


def test_a_declaration_covered_by_a_bind_is_accounted_for(tree: Path) -> None:
    body = "    image: db:1\n    volumes:\n      - type: bind\n        source: ./d\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body + "        target: /var/lib/db\n"))
    assert _faults(tree) == []


def test_a_mount_over_the_parent_directory_does_not_cover_the_declaration(tree: Path) -> None:
    """Docker's declaration is at a path, and a mount one level up leaves it standing."""
    body = "    image: db:1\n    volumes:\n      - db-data:/var/lib\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body))
    assert len(_faults(tree)) == 1


def test_an_image_declaring_nothing_needs_no_mount(tree: Path) -> None:
    _write(tree, "docker/docker-compose.c.yml", _service("    image: cache:1\n", name="cache"))
    assert _faults(tree) == []


def test_two_services_running_one_declaring_image_are_two_containers(tree: Path) -> None:
    """The memory stack's own shape: the server and its pg_dump sidecar run the same image, and
    each gets its own anonymous volume, so covering one says nothing about the other."""
    body = "    image: db:1\n    tmpfs:\n      - /var/lib/db\n"
    _write(
        tree, "docker/docker-compose.db.yml", _service(body) + _service("    image: db:1\n", "s")
    )
    faults = _faults(tree)
    assert len(faults) == 1
    assert "service 's'" in faults[0].detail


def test_a_service_naming_neither_an_image_nor_a_build_asks_nothing(tree: Path) -> None:
    """Every override re-opens a service to add environment; the image stays the base file's.

    The fragment is deliberately named something the record has no row for, because a fragment
    read as a definition would be keyed on `tree-worker` and the miss would be silent otherwise.
    """
    _write(
        tree, "docker/docker-compose.o.yml", _service("    environment:\n      A: b\n", "worker")
    )
    assert _faults(tree) == []
    assert volumecheck.check(tree, RECORDS).definitions == 1


def test_a_service_that_only_builds_is_keyed_as_the_project_and_its_own_name(tree: Path) -> None:
    """`tree-brain` is the row, because that is the image compose tags what it builds."""
    assert volumecheck.check(tree, RECORDS).names == ("tree-brain",)


def test_an_override_inherits_the_base_files_project(tree: Path) -> None:
    """An override pins no name of its own, so a build there is still the base's project."""
    _write(tree, "docker/docker-compose.b.yml", _service("    build: ./b\n", "brain"))
    assert volumecheck.check(tree, RECORDS).names == ("tree-brain",)


def test_a_file_pinning_its_own_project_keys_its_builds_under_that_one(tree: Path) -> None:
    """The probe stack's shape: its own project name, so its own image names."""
    text = "name: probe\n" + _service("    build: ./p\n", "sidecar")
    _write(tree, "docker/docker-compose.probe.yml", text)
    assert "probe-sidecar" in volumecheck.check(tree, RECORDS).names


# ── the second rule: what a Dockerfile here declares ───────────────────────────


def test_a_dockerfile_here_declaring_a_path_its_row_denies_is_reported(tree: Path) -> None:
    """The record moving under the gate from inside the tree, which is the reason this rule
    exists: nothing else here would notice until somebody rebuilt and re-derived by hand."""
    _write(tree, "brain/Dockerfile", "FROM scratch\nVOLUME /var/cache/thing\n")
    faults = _faults(tree)
    assert len(faults) == 1
    assert (faults[0].path, faults[0].line) == ("docker/docker-compose.yml", 3)
    assert "brain/Dockerfile declares VOLUME '/var/cache/thing'" in faults[0].detail
    assert "'tree-brain'" in faults[0].detail


def test_one_dockerfile_is_asked_once_per_row_it_builds(tree: Path) -> None:
    """`brain/Dockerfile` builds two of this repo's rows, and a path it declares goes uncarried by
    each of them separately: two images, two records, two containers collecting a volume."""
    _write(tree, "docker/docker-compose.email.yml", _service("    build: ./brain\n", "mail"))
    _write(tree, "brain/Dockerfile", "FROM scratch\nVOLUME /var/cache/thing\n")
    records = {**RECORDS, "tree-mail": ()}
    faults = [fault for fault in volumecheck.check(tree, records).faults if fault.line]
    assert [fault.path for fault in faults] == [
        "docker/docker-compose.email.yml",
        "docker/docker-compose.yml",
    ]


def test_a_build_reaching_no_dockerfile_is_a_fault_not_a_silent_pass(tree: Path) -> None:
    _write(tree, "docker/docker-compose.g.yml", _service("    build: ./gone\n", "brain"))
    faults = [fault for fault in _faults(tree) if fault.path.endswith("compose.g.yml")]
    assert len(faults) == 1
    assert "where no Dockerfile lands" in faults[0].detail


def test_the_walk_names_the_dockerfiles_it_followed_the_builds_to(tree: Path) -> None:
    """The reading behind the rule: a build the walk never resolved would check nothing."""
    assert volumecheck.check(tree, RECORDS).dockerfiles == ("brain/Dockerfile",)


def test_an_unrecorded_image_is_not_asked_what_its_dockerfile_declares(tree: Path) -> None:
    """There is no row to compare against yet, and the unrecorded fault already says so once."""
    _write(tree, "docker/docker-compose.n.yml", _service("    build: .\n", "fresh"))
    scanned = volumecheck.check(tree, RECORDS)
    assert scanned.dockerfiles == ("brain/Dockerfile",)
    assert [fault.line for fault in _faults(tree)] == [2]


# ── failing closed ─────────────────────────────────────────────────────────────


def test_an_image_the_record_has_no_row_for_is_an_unasked_question(tree: Path) -> None:
    _write(tree, "docker/docker-compose.n.yml", _service("    image: novel:9\n", name="n"))
    faults = _faults(tree)
    assert len(faults) == 1
    assert "has no row for" in faults[0].detail
    assert "just image-volumes" in faults[0].detail


def test_a_row_no_compose_file_names_is_a_claim_nothing_can_check(tree: Path) -> None:
    """The other direction: an image dropped from the tree leaves a row that says nothing true."""
    faults = volumecheck.check(tree, RECORDS).faults
    assert [fault.path for fault in faults] == [volumecheck.RECORD_PATH] * 2
    assert [fault.line for fault in faults] == [0, 0]
    assert "'cache:1'" in faults[0].detail
    assert "'db:1'" in faults[1].detail


def test_an_image_written_as_a_substitution_cannot_be_keyed_on(tree: Path) -> None:
    """The record is keyed on the image a container runs, which an expansion does not spell."""
    _write(tree, "docker/docker-compose.v.yml", _service('    image: "${TAG:-db:1}"\n'))
    faults = [fault for fault in _faults(tree) if fault.path.endswith("compose.v.yml")]
    assert len(faults) == 1
    assert "does not spell" in faults[0].detail


def test_a_build_with_no_project_to_key_it_under_is_a_fault(tmp_path: Path) -> None:
    """No bare-stemmed base file, so nothing says what `<project>-brain` resolves to."""
    _write(tmp_path, "docker/docker-compose.only.yml", _service("    build: ./b\n", "brain"))
    faults = [fault for fault in volumecheck.check(tmp_path, RECORDS).faults if fault.line]
    assert len(faults) == 1
    assert "no base compose file pins one project name" in faults[0].detail


def test_two_base_files_pinning_two_projects_are_not_guessed_between(tree: Path) -> None:
    """Several answers is as unanswerable as none, and a wrong row would be silent.

    The build that goes unkeyed is the one in an override, which is the only kind that has to
    inherit: a file pinning its own project answers for its own services either way.
    """
    _write(tree, "compose.yml", "name: other\nservices:\n  x:\n    image: cache:1\n")
    _write(tree, "docker/docker-compose.b.yml", _service("    build: ./b\n", "worker"))
    faults = [fault for fault in volumecheck.check(tree, RECORDS).faults if fault.line]
    assert len(faults) == 1
    assert "no base compose file pins one project name" in faults[0].detail


def test_a_compose_file_the_reader_refuses_is_a_fault(tree: Path) -> None:
    _write(tree, "docker/docker-compose.bad.yml", _service("    volumes:\n      - /x\n"))
    faults = [fault for fault in _faults(tree) if fault.path.endswith("compose.bad.yml")]
    assert len(faults) == 1
    assert (faults[0].line, "is not source:target" in faults[0].detail) == (0, True)


def test_a_compose_file_that_is_not_text_is_a_fault(tree: Path) -> None:
    (tree / "docker" / "docker-compose.raw.yml").write_bytes(b"\xff\xfe not utf-8")
    faults = [fault for fault in _faults(tree) if fault.path.endswith("compose.raw.yml")]
    assert len(faults) == 1
    assert faults[0].line == 0


def test_a_tree_with_no_compose_file_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    """A scan whose glob matched nothing reporting OK is the defect every gate here avoids."""
    with pytest.raises(volumecheck.ComposeSearchError, match="matched nothing cannot fail"):
        volumecheck.check(tmp_path, RECORDS)


# ── what the walk read ─────────────────────────────────────────────────────────


def test_check_counts_the_files_definitions_declarations_and_images_it_read(tree: Path) -> None:
    """Four numbers, none derivable from another: one image is named twice and most declare none."""
    body = "    image: db:1\n    tmpfs:\n      - /var/lib/db\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body) + _service(body, "s"))
    _write(tree, "docker/docker-compose.c.yml", _service("    image: cache:1\n", name="cache"))
    scanned = volumecheck.check(tree, RECORDS)
    assert (scanned.files, scanned.definitions, scanned.declared) == (3, 4, 2)
    assert scanned.names == ("cache:1", "db:1", "tree-brain")
    assert scanned.faults == []


# ── the repo this gate guards ──────────────────────────────────────────────────


def test_the_repo_itself_is_clean() -> None:
    """The gate's own assertion, run as a test so the scripts suite catches drift too."""
    assert volumecheck.check(REPO_ROOT).faults == []


def test_the_repo_really_declares_volumes_for_this_gate_to_have_checked() -> None:
    """A guard on the guard: nothing declared would make the test above vacuously green."""
    scanned = volumecheck.check(REPO_ROOT)
    assert scanned.declared >= 4, scanned
    assert scanned.definitions >= 8, scanned
    assert set(scanned.names) == set(IMAGE_VOLUMES), scanned.names


def test_the_repo_really_builds_from_dockerfiles_for_the_second_rule_to_have_read() -> None:
    """The other guard on the guard: three rows are built here, from these two files, and a walk
    that resolved neither would pass the tree while a `VOLUME` sat in one of them."""
    scanned = volumecheck.check(REPO_ROOT)
    assert scanned.dockerfiles == ("brain/Dockerfile", "brain/Dockerfile.modelhost")
    assert len(scanned.built) == 3, scanned.built


# ── the CLI ────────────────────────────────────────────────────────────────────


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert volumecheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "volumecheck OK" in capsys.readouterr().out


def test_main_states_what_it_read_beside_the_verdict(capsys: pytest.CaptureFixture[str]) -> None:
    assert volumecheck.main(["--root", str(REPO_ROOT)]) == 0
    out = capsys.readouterr().out
    assert "declared volume path(s)" in out
    assert "compose file(s), " in out
    assert "service definition(s) and " in out
    assert "2 Dockerfile(s) here declare nothing their row does not carry" in out


def test_main_reports_each_fault_and_exits_one(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tree, "docker/docker-compose.db.yml", _service("    image: db:1\n"))
    assert volumecheck.main(["--root", str(tree)]) == 1
    captured = capsys.readouterr()
    assert "docker/docker-compose.db.yml:2:" in captured.out
    assert "go uncovered or unrecorded" in captured.err


def test_main_rejects_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert volumecheck.main(["--root", str(tmp_path / "nope")]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_main_reports_a_scan_that_could_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert volumecheck.main(["--root", str(tmp_path)]) == 2
    assert "no compose file" in capsys.readouterr().err


# ── rederiving from a real docker ──────────────────────────────────────────────


def test_the_walk_names_the_images_this_repo_builds_apart() -> None:
    """The gate has no use for the distinction and a re-derivation cannot do without it: a built

    image has no registry to be refreshed from before it is asked what it declares.
    """
    scanned = volumecheck.check(REPO_ROOT)
    assert set(scanned.built) <= set(scanned.names)
    assert scanned.built == ("cortex-brain", "cortex-mcp-email", "cortex-model-host")


def test_a_service_that_only_builds_is_named_among_the_built(tree: Path) -> None:
    """The name compose runs it under, which is the project and the service and no registry."""
    _write(tree, "docker/docker-compose.extra.yml", _service("    build: ..\n", name="fresh"))
    assert volumecheck.check(tree, {}).built == ("tree-brain", "tree-fresh")


def test_main_rederiving_asks_the_registry_for_everything_it_did_not_build(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The count in the success line is the reading that says which half was refreshed."""
    asked: dict[str, bool] = {}

    def inspect(reference: str, *, pull: bool) -> tuple[str, ...]:
        asked[reference] = pull
        return IMAGE_VOLUMES[reference]

    assert volumecheck.main(["--root", str(REPO_ROOT), "--rederive"], inspect) == 0
    assert sorted(name for name, pull in asked.items() if not pull) == [
        "cortex-brain",
        "cortex-mcp-email",
        "cortex-model-host",
    ]
    assert "3 of them built here and the rest pulled" in capsys.readouterr().out


def test_main_rederiving_against_a_docker_that_agrees_reports_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["--root", str(REPO_ROOT), "--rederive"]
    assert volumecheck.main(argv, _answering(IMAGE_VOLUMES)) == 0
    assert f"agrees with docker on all {len(IMAGE_VOLUMES)} image(s)" in capsys.readouterr().out


def test_main_rederiving_against_a_docker_that_has_moved_reports_the_row(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """What `just image-volumes` is for: the image changed under the answer this repo recorded."""
    moved = {**IMAGE_VOLUMES, "redis:8-alpine": ("/data",)}
    argv = ["--root", str(REPO_ROOT), "--rederive"]
    assert volumecheck.main(argv, _answering(moved)) == 1
    captured = capsys.readouterr()
    assert "redis:8-alpine: recorded nothing, docker says /data" in captured.out
    assert "1 recorded row(s) disagree with docker" in captured.err
