from collections.abc import Mapping
from pathlib import Path

import pytest

import volumecheck
from imagedrift import InspectError, Inspector
from imagevolumes import IMAGE_VOLUMES, Row

REPO_ROOT = Path(__file__).resolve().parents[2]

RECORDS: dict[str, Row] = {
    "cache:1": Row((), ()),
    "db:1": Row(("/var/lib/db",), ()),
    "tree-brain": Row((), ()),
}

BASE = "name: tree\nservices:\n  brain:\n    build: ./brain\n"


def _write(root: Path, name: str, text: str) -> Path:
    """Write one compose file into the test tree, creating its directory when needed."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _service(body: str, name: str = "db") -> str:
    """Return the text of one override file declaring a single service."""
    return f"services:\n  {name}:\n{body}"


def _answering(answers: Mapping[str, Row]) -> Inspector:
    """Return an inspector that reads from a dict and raises on anything else, as docker does."""

    def inspect(reference: str, *, pull: bool) -> Row:  # noqa: ARG001
        try:
            return answers[reference]
        except KeyError as err:
            msg = f"docker image inspect failed: no such image: {reference}"
            raise InspectError(msg) from err

    return inspect


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Return a tree with the base compose file and the Dockerfile its one build stanza names."""
    _write(tmp_path, "docker/docker-compose.yml", BASE)
    _write(tmp_path, "brain/Dockerfile", "FROM scratch\n")
    return tmp_path


def _faults(tree: Path) -> list[volumecheck.Fault]:
    """Return every fault about the tree itself, which is all of them except the stale rows."""
    return [
        fault
        for fault in volumecheck.check(tree, RECORDS).faults
        if fault.path != volumecheck.RECORD_PATH
    ]


def test_a_declared_volume_the_service_mounts_nothing_at_is_reported(tree: Path) -> None:
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
    body = "    image: db:1\n    tmpfs:\n      - /var/lib/db\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body))
    assert _faults(tree) == []


def test_a_declaration_covered_by_a_bind_is_accounted_for(tree: Path) -> None:
    body = "    image: db:1\n    volumes:\n      - type: bind\n        source: ./d\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body + "        target: /var/lib/db\n"))
    assert _faults(tree) == []


def test_a_mount_over_the_parent_directory_does_not_cover_the_declaration(tree: Path) -> None:
    body = "    image: db:1\n    volumes:\n      - db-data:/var/lib\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body))
    assert len(_faults(tree)) == 1


def test_an_image_declaring_nothing_needs_no_mount(tree: Path) -> None:
    _write(tree, "docker/docker-compose.c.yml", _service("    image: cache:1\n", name="cache"))
    assert _faults(tree) == []


def test_two_services_running_one_declaring_image_are_two_containers(tree: Path) -> None:
    body = "    image: db:1\n    tmpfs:\n      - /var/lib/db\n"
    _write(
        tree, "docker/docker-compose.db.yml", _service(body) + _service("    image: db:1\n", "s")
    )
    faults = _faults(tree)
    assert len(faults) == 1
    assert "service 's'" in faults[0].detail


def test_a_service_naming_neither_an_image_nor_a_build_asks_nothing(tree: Path) -> None:
    _write(
        tree, "docker/docker-compose.o.yml", _service("    environment:\n      A: b\n", "worker")
    )
    assert _faults(tree) == []
    assert volumecheck.check(tree, RECORDS).definitions == 1


def test_a_service_that_only_builds_is_keyed_as_the_project_and_its_own_name(tree: Path) -> None:
    assert volumecheck.check(tree, RECORDS).names == ("tree-brain",)


def test_an_override_inherits_the_base_files_project(tree: Path) -> None:
    _write(tree, "docker/docker-compose.b.yml", _service("    build: ./b\n", "brain"))
    assert volumecheck.check(tree, RECORDS).names == ("tree-brain",)


def test_a_file_naming_its_own_project_keys_its_builds_under_that_one(tree: Path) -> None:
    text = "name: probe\n" + _service("    build: ./p\n", "sidecar")
    _write(tree, "docker/docker-compose.probe.yml", text)
    assert "probe-sidecar" in volumecheck.check(tree, RECORDS).names


def test_a_dockerfile_here_declaring_a_path_its_row_denies_is_reported(tree: Path) -> None:
    _write(tree, "brain/Dockerfile", "FROM scratch\nVOLUME /var/cache/thing\n")
    faults = _faults(tree)
    assert len(faults) == 1
    assert (faults[0].path, faults[0].line) == ("docker/docker-compose.yml", 3)
    assert "brain/Dockerfile declares VOLUME '/var/cache/thing'" in faults[0].detail
    assert "'tree-brain'" in faults[0].detail


def test_one_dockerfile_is_asked_once_per_row_it_builds(tree: Path) -> None:
    _write(tree, "docker/docker-compose.email.yml", _service("    build: ./brain\n", "mail"))
    _write(tree, "brain/Dockerfile", "FROM scratch\nVOLUME /var/cache/thing\n")
    records = {**RECORDS, "tree-mail": Row((), ())}
    faults = [fault for fault in volumecheck.check(tree, records).faults if fault.line]
    assert [fault.path for fault in faults] == [
        "docker/docker-compose.email.yml",
        "docker/docker-compose.yml",
    ]


def test_a_build_reaching_no_dockerfile_is_unasked_not_a_silent_pass(tree: Path) -> None:
    _write(tree, "docker/docker-compose.g.yml", _service("    build: ./gone\n", "brain"))
    scanned = volumecheck.check(tree, RECORDS)
    assert [fault.path for fault in scanned.unasked] == ["docker/docker-compose.g.yml"]
    assert "where no Dockerfile exists" in scanned.unasked[0].detail
    assert [fault for fault in scanned.findings if fault.path.endswith("compose.g.yml")] == []


def test_the_walk_names_the_dockerfiles_it_followed_the_builds_to(tree: Path) -> None:
    assert volumecheck.check(tree, RECORDS).dockerfiles == ("brain/Dockerfile",)


def test_an_unrecorded_image_is_not_asked_what_its_dockerfile_declares(tree: Path) -> None:
    _write(tree, "docker/docker-compose.n.yml", _service("    build: .\n", "fresh"))
    scanned = volumecheck.check(tree, RECORDS)
    assert scanned.dockerfiles == ("brain/Dockerfile",)
    assert [fault.line for fault in _faults(tree)] == [2]


def test_an_image_the_record_has_no_row_for_is_an_unasked_question(tree: Path) -> None:
    _write(tree, "docker/docker-compose.n.yml", _service("    image: novel:9\n", name="n"))
    faults = _faults(tree)
    assert len(faults) == 1
    assert "has no row for" in faults[0].detail
    assert "just image-volumes" in faults[0].detail


def test_a_row_no_compose_file_names_is_a_claim_nothing_can_check(tree: Path) -> None:
    faults = volumecheck.check(tree, RECORDS).faults
    assert [fault.path for fault in faults] == [volumecheck.RECORD_PATH] * 2
    assert [fault.line for fault in faults] == [0, 0]
    assert "'cache:1'" in faults[0].detail
    assert "'db:1'" in faults[1].detail


def test_a_path_the_base_declares_and_the_built_row_lacks_is_reported(tree: Path) -> None:
    _write(tree, "brain/Dockerfile", "FROM base:1\n")
    records = {**RECORDS, "base:1": Row(("/inherited",), ())}
    scanned = volumecheck.check(tree, records)
    faults = [fault for fault in scanned.faults if fault.path != volumecheck.RECORD_PATH]
    assert len(faults) == 1
    assert "FROM 'base:1', which declares VOLUME '/inherited'" in faults[0].detail


def test_a_base_the_record_has_no_row_for_is_an_unasked_question(tree: Path) -> None:
    _write(tree, "brain/Dockerfile", "FROM base:1\n")
    faults = _faults(tree)
    assert len(faults) == 1
    assert "has no row for" in faults[0].detail
    assert "just image-volumes" in faults[0].detail


def test_a_row_named_only_by_a_dockerfile_is_named_enough_to_stand(tree: Path) -> None:
    _write(tree, "brain/Dockerfile", "FROM base:1\n")
    scanned = volumecheck.check(tree, {**RECORDS, "base:1": Row((), ())})
    assert "base:1" in scanned.names
    assert [fault for fault in scanned.faults if "'base:1'" in fault.detail] == []


def test_an_image_written_as_a_substitution_is_unasked_rather_than_keyed_on(tree: Path) -> None:
    _write(tree, "docker/docker-compose.v.yml", _service('    image: "${TAG:-db:1}"\n'))
    scanned = volumecheck.check(tree, RECORDS)
    assert [fault.path for fault in scanned.unasked] == ["docker/docker-compose.v.yml"]
    assert "does not name" in scanned.unasked[0].detail
    assert [fault for fault in scanned.findings if fault.path.endswith("compose.v.yml")] == []


def test_a_build_with_no_project_to_key_it_under_is_unasked(tmp_path: Path) -> None:
    _write(tmp_path, "docker/docker-compose.only.yml", _service("    build: ./b\n", "brain"))
    scanned = volumecheck.check(tmp_path, RECORDS)
    assert [fault.line for fault in scanned.unasked] == [2]
    assert "no base compose file sets one project name" in scanned.unasked[0].detail
    assert [fault for fault in scanned.findings if fault.line] == []


def test_two_base_files_naming_two_projects_are_not_guessed_between(tree: Path) -> None:
    _write(tree, "compose.yml", "name: other\nservices:\n  x:\n    image: cache:1\n")
    _write(tree, "docker/docker-compose.b.yml", _service("    build: ./b\n", "worker"))
    faults = [fault for fault in volumecheck.check(tree, RECORDS).faults if fault.line]
    assert len(faults) == 1
    assert "no base compose file sets one project name" in faults[0].detail


def test_a_compose_file_the_reader_refuses_is_a_refused_file_not_a_finding(tree: Path) -> None:
    _write(tree, "docker/docker-compose.bad.yml", _service("    volumes:\n      - /x\n"))
    scanned = volumecheck.check(tree, {"tree-brain": Row((), ())})
    assert [fault.path for fault in scanned.refused] == ["docker/docker-compose.bad.yml"]
    assert (scanned.refused[0].line, "is not source:target" in scanned.refused[0].detail) == (
        0,
        True,
    )
    assert scanned.findings == []


def test_a_compose_file_that_is_not_text_is_a_refused_file(tree: Path) -> None:
    (tree / "docker" / "docker-compose.raw.yml").write_bytes(b"\xff\xfe not utf-8")
    scanned = volumecheck.check(tree, {"tree-brain": Row((), ())})
    assert [(fault.path, fault.line) for fault in scanned.refused] == [
        ("docker/docker-compose.raw.yml", 0)
    ]
    assert scanned.findings == []
    assert scanned.faults == [*scanned.refused]


def test_a_tree_with_no_compose_file_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises(volumecheck.ComposeSearchError, match="matched nothing cannot fail"):
        volumecheck.check(tmp_path, RECORDS)


def test_check_counts_the_files_definitions_declarations_and_images_it_read(tree: Path) -> None:
    body = "    image: db:1\n    tmpfs:\n      - /var/lib/db\n"
    _write(tree, "docker/docker-compose.db.yml", _service(body) + _service(body, "s"))
    _write(tree, "docker/docker-compose.c.yml", _service("    image: cache:1\n", name="cache"))
    scanned = volumecheck.check(tree, RECORDS)
    assert (scanned.files, scanned.definitions, scanned.declared) == (3, 4, 2)
    assert scanned.names == ("cache:1", "db:1", "tree-brain")
    assert scanned.faults == []


def test_the_repo_itself_is_clean() -> None:
    assert volumecheck.check(REPO_ROOT).faults == []


def test_the_repo_really_declares_volumes_for_this_gate_to_have_checked() -> None:
    scanned = volumecheck.check(REPO_ROOT)
    assert scanned.declared >= 4, scanned
    assert scanned.definitions >= 8, scanned
    assert set(scanned.names) == set(IMAGE_VOLUMES), scanned.names


def test_the_repo_really_builds_from_dockerfiles_for_the_second_rule_to_have_read() -> None:
    scanned = volumecheck.check(REPO_ROOT)
    assert scanned.dockerfiles == ("brain/Dockerfile", "brain/Dockerfile.modelhost")
    assert len(scanned.built) == 3, scanned.built


def test_main_passes_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert volumecheck.main(["--root", str(REPO_ROOT)]) == 0
    assert "volumecheck OK" in capsys.readouterr().out


def test_main_states_what_it_read_beside_the_result(capsys: pytest.CaptureFixture[str]) -> None:
    assert volumecheck.main(["--root", str(REPO_ROOT)]) == 0
    out = capsys.readouterr().out
    assert "declared volume path(s)" in out
    assert "compose file(s), " in out
    assert "service definition(s) and " in out
    assert "image(s) counting the bases those builds stand on, " in out
    assert "2 Dockerfile(s) here declare and inherit nothing their row does not contain" in out
    assert "does not contain, triggers included" in out


_REFUSED = (
    "\nvolumecheck: 1 compose file(s) could not be read, so no service in them was checked. "
    "Rewrite a form the reader refuses in one it takes, or save the file as UTF-8 text, as the "
    "file's own fault says.\n"
)


def _findings(count: int) -> str:
    """Return the whole summary line a run with ``count`` findings ends with."""
    return (
        f"\nvolumecheck: {count} image volume declaration(s) go uncovered or unrecorded. Mount "
        f"something at the path, or bring {volumecheck.RECORD_PATH} back in step with the tree by "
        "running `just image-volumes`.\n"
    )


def test_main_reports_each_fault_and_exits_one(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tree, "docker/docker-compose.db.yml", _service("    image: db:1\n"))
    assert volumecheck.main(["--root", str(tree)]) == 1
    captured = capsys.readouterr()
    assert "docker/docker-compose.db.yml:2:" in captured.out
    assert captured.err == _findings(2 + len(IMAGE_VOLUMES))


def test_main_counts_a_refused_file_as_a_file_and_not_as_a_declaration(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tree / "docker" / "docker-compose.raw.yml").write_bytes(b"\xff\xfe not utf-8")
    assert volumecheck.main(["--root", str(tree)]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("docker/docker-compose.raw.yml:0: 'utf-8' codec can't decode")
    assert captured.err == _REFUSED + _findings(1 + len(IMAGE_VOLUMES))


_UNASKED = (
    "\nvolumecheck: 1 image(s) could not be asked what they declare, because the image a service "
    "runs could not be named or the Dockerfile that builds it could not be read, so nothing was "
    "compared with the record. Write the name or the path out, as each one's own fault says.\n"
)


def test_main_counts_an_unasked_image_apart_from_the_declarations(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tree, "docker/docker-compose.v.yml", _service('    image: "${TAG}"\n'))
    assert volumecheck.main(["--root", str(tree)]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("docker/docker-compose.v.yml:2: service 'db' names its image")
    assert captured.err == _UNASKED + _findings(1 + len(IMAGE_VOLUMES))


def test_main_fails_a_run_whose_only_fault_is_a_refused_file(
    tree: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    real = volumecheck.check

    def exact(root: Path) -> volumecheck.Scan:
        return real(root, {"tree-brain": Row((), ())})

    monkeypatch.setattr(volumecheck, "check", exact)
    (tree / "docker" / "docker-compose.raw.yml").write_bytes(b"\xff\xfe not utf-8")
    assert volumecheck.main(["--root", str(tree)]) == 1
    assert capsys.readouterr().err == _REFUSED


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


def test_the_walk_names_the_images_this_repo_builds_apart() -> None:
    scanned = volumecheck.check(REPO_ROOT)
    assert set(scanned.built) <= set(scanned.names)
    assert scanned.built == ("cortex-brain", "cortex-mcp-email", "cortex-model-host")


def test_a_service_that_only_builds_is_named_among_the_built(tree: Path) -> None:
    _write(tree, "docker/docker-compose.extra.yml", _service("    build: ..\n", name="fresh"))
    assert volumecheck.check(tree, {}).built == ("tree-brain", "tree-fresh")


def test_main_rederiving_asks_the_registry_for_everything_it_did_not_build(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asked: dict[str, bool] = {}

    def inspect(reference: str, *, pull: bool) -> Row:
        asked[reference] = pull
        return IMAGE_VOLUMES[reference]

    assert volumecheck.main(["--root", str(REPO_ROOT), "--recompute"], inspect) == 0
    assert sorted(name for name, pull in asked.items() if not pull) == [
        "cortex-brain",
        "cortex-mcp-email",
        "cortex-model-host",
    ]
    assert "3 of them built here and the rest pulled" in capsys.readouterr().out


def test_main_rederiving_against_a_docker_that_agrees_reports_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["--root", str(REPO_ROOT), "--recompute"]
    assert volumecheck.main(argv, _answering(IMAGE_VOLUMES)) == 0
    assert f"agrees with docker on all {len(IMAGE_VOLUMES)} image(s)" in capsys.readouterr().out


def test_main_rederiving_against_a_docker_that_has_moved_reports_the_row(
    capsys: pytest.CaptureFixture[str],
) -> None:
    moved = {**IMAGE_VOLUMES, "redis:8-alpine": Row(("/data",), ())}
    argv = ["--root", str(REPO_ROOT), "--recompute"]
    assert volumecheck.main(argv, _answering(moved)) == 1
    captured = capsys.readouterr()
    assert "redis:8-alpine: recorded nothing, docker says /data" in captured.out
    assert "1 recorded reading(s) disagree with docker" in captured.err
