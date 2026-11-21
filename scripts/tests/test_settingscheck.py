from pathlib import Path

import pytest

from settingscheck import (
    EXEMPT,
    Exemption,
    SettingsCheckError,
    check,
    held,
    image_command,
    main,
    module_run,
    read_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SETTINGS = (
    "class Demo(BaseSettings):\n"
    "    model_config = SettingsConfigDict(env_prefix='CORTEX_DEMO_', env_nested_delimiter='__')\n"
    "    level: str = 'info'\n"
    "    port: int = 1\n"
    "    costs: dict[str, int] = {}\n"
)
PORT = Exemption("CORTEX_DEMO_PORT", "the base file fixes it")

BASE = """name: demo
services:
  app:
    build: ./app
    environment:
      CORTEX_DEMO_LEVEL:
  cache:
    image: redis
    environment:
      CORTEX_DEMO_COSTS:
"""
OVERLAY = """services:
  app:
    environment:
      CORTEX_DEMO_COSTS__SPAWN: "4"
"""


def tree(root: Path, base: str = BASE, overlay: str = OVERLAY, cmd: str | None = None) -> Path:
    """Write the fixture tree under ``root`` and return it."""
    module = root / "brain/packages/demo/src/cortex_demo"
    module.mkdir(parents=True)
    (module / "config.py").write_text(SETTINGS, encoding="utf-8")
    (root / "app").mkdir()
    written = '["python", "-m", "cortex_demo"]' if cmd is None else cmd
    (root / "app/Dockerfile").write_text(f"FROM x AS b\nCMD {written}\n", encoding="utf-8")
    (root / "docker").mkdir()
    (root / "docker/docker-compose.yml").write_text(base, encoding="utf-8")
    (root / "docker/docker-compose.extra.yml").write_text(overlay, encoding="utf-8")
    return root


def test_module_run_reads_the_word_after_the_module_flag() -> None:
    assert module_run(("python", "-m", "cortex_demo", "--x")) == "cortex_demo"
    assert module_run(("python", "server.py")) is None
    assert module_run(("python", "-m")) is None


def test_image_command_reads_the_last_exec_form_cmd(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text('CMD ["a"]\nFROM y\n  CMD ["b", "c"]  \n', encoding="utf-8")
    assert image_command(dockerfile) == ("b", "c")
    dockerfile.write_text("FROM y\n", encoding="utf-8")
    assert image_command(dockerfile) is None


@pytest.mark.parametrize(
    ("written", "detail"),
    [("python -m app", "is not the exec form"), ('{"a": 1}', "is not a list")],
)
def test_image_command_raises_on_a_cmd_it_cannot_read(
    tmp_path: Path, written: str, detail: str
) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text(f"CMD {written}\n", encoding="utf-8")
    with pytest.raises(SettingsCheckError, match=detail):
        image_command(dockerfile)


def test_the_stack_merges_keys_and_takes_argv_from_command_or_image(tmp_path: Path) -> None:
    base = BASE + (
        "  runner:\n    build: ./app\n    command: ['python', '-m', 'other']\n"
        "  lost:\n    build: ./nowhere\n"
    ).replace("'", '"')
    stack = read_stack(tree(tmp_path, base=base))
    assert stack.files == 2
    assert stack.argv == {
        "app": ("python", "-m", "cortex_demo"),
        "runner": ("python", "-m", "other"),
    }
    assert stack.keys["app"] == frozenset({"CORTEX_DEMO_LEVEL", "CORTEX_DEMO_COSTS__SPAWN"})


def test_an_image_without_a_cmd_runs_nothing_this_scan_can_hold(tmp_path: Path) -> None:
    stack = read_stack(tree(tmp_path, cmd='["x"]'))
    assert stack.argv == {"app": ("x",)}
    (tmp_path / "app/Dockerfile").write_text("FROM x\n", encoding="utf-8")
    assert read_stack(tmp_path).argv == {}


def test_two_commands_for_one_service_raise(tmp_path: Path) -> None:
    overlay = OVERLAY + '    command: ["python", "-m", "a"]\n'
    base = BASE.replace("    build: ./app\n", '    build: ./app\n    command: ["b"]\n')
    with pytest.raises(SettingsCheckError, match="app is started with two different commands"):
        read_stack(tree(tmp_path, base=base, overlay=overlay))


def test_the_same_command_in_two_files_is_one_answer(tmp_path: Path) -> None:
    command = '    command: ["python", "-m", "cortex_demo"]\n'
    base = BASE.replace("    build: ./app\n", "    build: ./app\n" + command)
    assert read_stack(tree(tmp_path, base=base, overlay=OVERLAY + command)).argv == {
        "app": ("python", "-m", "cortex_demo")
    }


def test_a_complete_stack_passes_with_the_exempt_field_unnamed(tmp_path: Path) -> None:
    scanned = check(tree(tmp_path), (PORT,))
    assert scanned.faults == []
    assert (scanned.services, scanned.classes, scanned.fields, scanned.files) == (
        ("app",),
        1,
        3,
        2,
    )


def test_a_field_named_by_no_file_for_its_service_fails(tmp_path: Path) -> None:
    base = BASE.replace("      CORTEX_DEMO_LEVEL:\n", "      CORTEX_DEMO_OTHER:\n")
    faults = check(tree(tmp_path, base=base), (PORT,)).faults
    assert [(fault.where, fault.detail) for fault in faults] == [
        (
            "brain/packages/demo/src/cortex_demo/config.py: Demo.CORTEX_DEMO_LEVEL",
            "reaches the app service from no compose file; add it as a bare key",
        )
    ]


def test_a_key_on_another_service_does_not_count(tmp_path: Path) -> None:
    faults = check(tree(tmp_path, overlay="services:\n  app:\n    init: true\n"), (PORT,)).faults
    assert [fault.where.rsplit(".", 1)[-1] for fault in faults] == ["CORTEX_DEMO_COSTS"]


def test_a_service_with_no_environment_owes_every_field(tmp_path: Path) -> None:
    base = BASE.replace("    environment:\n      CORTEX_DEMO_LEVEL:\n", "")
    faults = check(tree(tmp_path, base=base, overlay="services: {}\n"), (PORT,)).faults
    assert len(faults) == 2


@pytest.mark.parametrize("written", ['"${CORTEX_DEMO_LEVEL:-}"', "${CORTEX_DEMO_LEVEL-}"])
def test_an_empty_default_for_a_field_that_defaults_to_something_else_fails(
    tmp_path: Path, written: str
) -> None:
    base = BASE.replace("CORTEX_DEMO_LEVEL:\n", f"CORTEX_DEMO_LEVEL: {written}\n")
    faults = check(tree(tmp_path, base=base), (PORT,)).faults
    assert [(fault.where, fault.detail) for fault in faults] == [
        (
            "docker/docker-compose.yml: CORTEX_DEMO_LEVEL",
            "has an empty default for app, and Demo defaults it to something else, so unset it "
            "arrives empty; write it as a bare key",
        )
    ]


def test_an_empty_default_is_reported_once_at_the_first_file_writing_it(tmp_path: Path) -> None:
    emptied = '      CORTEX_DEMO_LEVEL: "${CORTEX_DEMO_LEVEL:-}"\n'
    base = BASE.replace("      CORTEX_DEMO_LEVEL:\n", emptied)
    stack = read_stack(tree(tmp_path, base=base, overlay=OVERLAY + emptied))
    assert stack.emptied == {"app": {"CORTEX_DEMO_LEVEL": "docker/docker-compose.extra.yml"}}
    assert len(check(tmp_path, (PORT,)).faults) == 1


@pytest.mark.parametrize(
    "written",
    ['"${CORTEX_DEMO_LEVEL:-info}"', '""', '"${CORTEX_DEMO_LEVEL:-}x"', '"${CORTEX_DEMO_LEVEL:?}"'],
)
def test_a_value_that_is_not_an_empty_default_is_not_one(tmp_path: Path, written: str) -> None:
    base = BASE.replace("CORTEX_DEMO_LEVEL:\n", f"CORTEX_DEMO_LEVEL: {written}\n")
    assert check(tree(tmp_path, base=base), (PORT,)).faults == []


def test_an_empty_default_passes_for_a_field_that_defaults_to_the_empty_string(
    tmp_path: Path,
) -> None:
    base = BASE.replace("CORTEX_DEMO_LEVEL:\n", 'CORTEX_DEMO_LEVEL: "${CORTEX_DEMO_LEVEL:-}"\n')
    tree(tmp_path, base=base)
    config = tmp_path / "brain/packages/demo/src/cortex_demo/config.py"
    config.write_text(SETTINGS.replace("'info'", "''"), encoding="utf-8")
    assert check(tmp_path, (PORT,)).faults == []


def test_an_empty_default_on_another_service_or_one_entry_of_a_map_is_not_read(
    tmp_path: Path,
) -> None:
    base = BASE.replace("CORTEX_DEMO_COSTS:\n", 'CORTEX_DEMO_LEVEL: "${CORTEX_DEMO_LEVEL:-}"\n')
    overlay = OVERLAY.replace('"4"', '"${CORTEX_DEMO_COSTS__SPAWN:-}"')
    scanned = check(tree(tmp_path, base=base, overlay=overlay), (PORT,))
    assert scanned.faults == []


def test_the_shipped_fields_an_empty_value_changes_do_not_default_to_the_empty_string() -> None:
    read = {
        field.name: field.empty_default
        for settings in held(REPO_ROOT, read_stack(REPO_ROOT)).values()
        for field in settings.fields
    }
    assert not read["CORTEX_REASONING_EFFORT_BRAIN"]
    assert not read["CORTEX_MODEL_FILE_CORTEX_DRAFT"]
    assert not read["CORTEX_MODEL_FILE_SUBAGENT_GPU_DRAFT"]
    assert read["CORTEX_EMAIL_SMTP_PASSWORD"]
    assert read["CORTEX_SEAM_TOKEN"]


def test_an_exemption_a_file_names_fails(tmp_path: Path) -> None:
    faults = check(tree(tmp_path, overlay=OVERLAY + "      CORTEX_DEMO_PORT:\n"), (PORT,)).faults
    assert [fault.detail for fault in faults] == [
        "is exempt, yet a compose file names it for app; drop the exemption"
    ]


def test_an_exemption_no_class_declares_fails(tmp_path: Path) -> None:
    gone = Exemption("CORTEX_DEMO_GONE", "renamed")
    faults = check(tree(tmp_path), (PORT, gone)).faults
    assert [(fault.where, fault.detail) for fault in faults] == [
        (
            "settingscheck.EXEMPT",
            "CORTEX_DEMO_GONE is exempt, but no settings class read here declares it",
        )
    ]


def test_a_stack_running_no_workspace_module_raises(tmp_path: Path) -> None:
    with pytest.raises(SettingsCheckError, match="a scan over nothing cannot fail"):
        check(tree(tmp_path, cmd='["python", "-m", "cortex_absent"]'))


def test_an_unreadable_tree_raises_the_scan_error(tmp_path: Path) -> None:
    with pytest.raises(SettingsCheckError, match="no compose file"):
        check(tmp_path)
    tree(tmp_path)
    (tmp_path / "brain/packages/demo/src/cortex_demo/config.py").write_text("(", encoding="utf-8")
    with pytest.raises(SettingsCheckError, match="cannot read"):
        check(tmp_path)


def test_main_reports_each_outcome(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(tmp_path / "absent")]) == 2
    assert main(["--root", str(tmp_path)]) == 2
    tree(tmp_path)
    assert main(["--root", str(tmp_path)]) == 1
    out, err = capsys.readouterr()
    assert "Demo.CORTEX_DEMO_PORT: reaches the app service from no compose file" in out
    assert "is not a directory" in err
    assert f"settingscheck: {1 + len(EXEMPT)} problem(s)" in err


def test_the_committed_tree_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(REPO_ROOT)]) == 0
    out, _ = capsys.readouterr()
    assert out.startswith("settingscheck OK: the ")
    assert "read by brain, mcp-email, model-host" in out


def test_every_shipped_exemption_names_a_real_field_and_says_why() -> None:
    scanned = check(REPO_ROOT)
    assert scanned.faults == []
    assert all(exemption.why for exemption in EXEMPT)
    assert len({exemption.name for exemption in EXEMPT}) == len(EXEMPT)
