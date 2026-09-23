from collections.abc import Sequence
from pathlib import Path

import pytest

import flagcheck
from artifactnames import Artifact
from flagcheck import (
    FlagCheckError,
    Server,
    check,
    check_one,
    main,
    unclassifiable,
)
from hostedtiers import MODEL_MANAGER
from subagentflags import REQUIREMENTS, Flag, Requirement

REPO_ROOT = Path(__file__).resolve().parents[2]

SUBAGENTS = "docker-compose.subagents.yml"
ROSTER = "docker-compose.subagents-roster.yml"

ARGV_MODULE = "tiers.py"
TIER_MODULE = "config.py"

KWARG_ITEMS = '      - "--chat-template-kwargs"\n      - \'{"enable_thinking": false}\'\n'
BUDGET_ITEMS = '      - "--reasoning-budget"\n      - "0"\n'
CACHE_ITEMS = '      - "--cache-ram"\n      - "0"\n'
JINJA_ITEM = '      - "--jinja"\n'

THREADS_ITEMS = '      - "--threads"\n      - "${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"\n'
NGL_ITEMS = '      - "-ngl"\n      - "0"\n'

HOSTED_TAIL = "                extra=_SUBAGENT_TAIL,\n"
HOSTED_JINJA = '_JINJA = "--jinja"'

HOSTED_ALIAS = '"CORTEX_MODEL_FILE_SUBAGENT_GPU"'
ARTIFACT_ITEM = '"/models/${CORTEX_MODEL_FILE_SUBAGENT:-'
MISSPELLED_ITEM = '"/models/${CORTEX_SUBAGENT_MODEL_FILE:-'

FOURTH_FIELD = "    subagent_gpu_port: int = Field(default=8083, gt=0, le=65535)\n"
FOURTH_TIER = "            ),\n        )\n        return tuple("
FOURTH = """\
            ),
            TierArgs(
                model="subagent-cpu",
                model_path=self._path(self.subagent_cpu_file),
                port=8084,
                ngl=0,
                ctx_size=4096,
                parallel=1,
            ),
        )
        return tuple("""

BARE_ARGV = """\
_JINJA = "--jinja"


def llama_server_argv(binary, tier):
    return (binary, _JINJA, *tier.extra)
"""

BARE_TIERS = """\
class ModelHostConfig(BaseSettings):
    cortex_file: str = Field(default="", validation_alias="CORTEX_MODEL_FILE_CORTEX")

    def tiers(self):
        return (TierArgs(model_path=self._path(self.cortex_file), extra=()),)
"""

THIRD = """\
services:
  brain:
    environment:
      CORTEX_SUBAGENTS_ROSTER__third: '{"endpoint": "http://llama-subagent-third:8084"}'

  llama-subagent-third:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      - "--model"
      - "/models/third.gguf"
      - "--port"
      - "8084"
      - "-ngl"
      - "0"
"""


def copied(root: Path, edits: Sequence[tuple[str, str, str]] = ()) -> Path:
    """Copy the committed tree under ``root``, applying each named edit to its file."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    (root / MODEL_MANAGER).mkdir(parents=True, exist_ok=True)
    sidecar = [REPO_ROOT / MODEL_MANAGER / name for name in (ARGV_MODULE, TIER_MODULE)]
    for path in [*(REPO_ROOT / "docker").glob("docker-compose*.yml"), *sidecar]:
        text = path.read_text(encoding="utf-8")
        for _, was, now in [edit for edit in edits if edit[0] == path.name]:
            assert was in text, f"{path.name} no longer writes {was!r}, so this mutation edits it"
            text = text.replace(was, now, 1)
        under = MODEL_MANAGER if path.suffix == ".py" else Path("docker")
        (root / under / path.name).write_text(text, encoding="utf-8")
    return root


def _server(*command: str) -> Server:
    """Return one server with the argv a test passes, which is all the rule reads."""
    return Server(file="docker/docker-compose.made-up.yml", service="one", line=1, command=command)


def test_a_server_with_every_required_flag_has_no_fault() -> None:
    argv = (
        "--jinja",
        "--chat-template-kwargs",
        '{"enable_thinking": false}',
        "--reasoning-budget",
        "0",
        "--cache-ram",
        "0",
    )
    assert check_one(_server(*argv)) == []


def test_a_fault_states_the_requirement_that_names_it_and_the_reason_it_exists() -> None:
    faults = check_one(_server("--jinja"))
    assert len(faults) == 3, faults
    pair = [fault for fault in faults if "reasoning-off pair:" in fault.detail]
    assert len(pair) == 2
    assert all(fault.detail.startswith("the tier's reasoning-off pair:") for fault in pair)
    assert all("only symptom is a slow subagent" in fault.detail for fault in pair)
    cache = [fault for fault in faults if "prompt cache, turned off:" in fault.detail]
    assert [fault.detail.split(":")[0] for fault in cache] == [
        "the host-RAM prompt cache, turned off"
    ]
    assert "the mapped weights a server reads on every token" in cache[0].detail
    assert {fault.service for fault in faults} == {"one"}


def test_the_committed_tree_is_green_so_every_red_below_is_the_mutation(tmp_path: Path) -> None:
    scanned = check(copied(tmp_path))
    assert scanned.faults == []
    assert scanned.servers >= 3, "two compose servers and the hosted tier, so two would be a miss"


def test_the_hosted_tier_is_held_by_the_same_rule_as_the_servers_compose_starts(
    tmp_path: Path,
) -> None:
    faults = check(copied(tmp_path, [(TIER_MODULE, HOSTED_TAIL, "                extra=(),\n")]))
    assert [fault.service for fault in faults.faults] == ["CORTEX_MODEL_FILE_SUBAGENT_GPU"] * 3
    assert {fault.file for fault in faults.faults} == {(MODEL_MANAGER / TIER_MODULE).as_posix()}
    assert sum("reasoning-off pair" in fault.detail for fault in faults.faults) == 2
    assert sum("prompt cache" in fault.detail for fault in faults.faults) == 1


def test_a_fourth_tier_for_a_second_pick_is_held_the_day_it_is_declared(tmp_path: Path) -> None:
    field = FOURTH_FIELD + (
        '    subagent_cpu_file: str = Field(\n        default="", '
        'validation_alias="CORTEX_MODEL_FILE_SUBAGENT_CPU"\n    )\n'
    )
    faults = check(
        copied(
            tmp_path,
            [(TIER_MODULE, FOURTH_FIELD, field), (TIER_MODULE, FOURTH_TIER, FOURTH)],
        )
    ).faults
    assert {fault.service for fault in faults} == {"CORTEX_MODEL_FILE_SUBAGENT_CPU"}
    assert len(faults) == 3, "the shared argv still carries --jinja, so only the tail is missing"


def test_a_sidecar_renaming_the_tool_capable_template_fails_its_own_tier(
    tmp_path: Path,
) -> None:
    edit = (ARGV_MODULE, HOSTED_JINJA, '_JINJA = "--chat-template"')
    faults = check(copied(tmp_path, [edit])).faults
    assert [fault.service for fault in faults] == ["CORTEX_MODEL_FILE_SUBAGENT_GPU"]
    assert faults[0].detail.startswith("the tool-capable chat template:")


@pytest.mark.parametrize("compose", [SUBAGENTS, ROSTER])
@pytest.mark.parametrize(("half", "items"), [("kwarg", KWARG_ITEMS), ("budget", BUDGET_ITEMS)])
def test_a_server_started_with_half_the_reasoning_off_pair_is_a_fault(
    tmp_path: Path, compose: str, half: str, items: str
) -> None:
    faults = check(copied(tmp_path, [(compose, items, "")])).faults
    assert len(faults) == 1, half
    assert faults[0].file == f"docker/{compose}"


@pytest.mark.parametrize("compose", [SUBAGENTS, ROSTER])
def test_a_server_started_on_the_engines_own_prompt_cache_is_a_fault(
    tmp_path: Path, compose: str
) -> None:
    faults = check(copied(tmp_path, [(compose, CACHE_ITEMS, "")])).faults
    assert [fault.file for fault in faults] == [f"docker/{compose}"]
    assert faults[0].detail.startswith("the host-RAM prompt cache, turned off:")
    assert "it has no --cache-ram" in faults[0].detail


def test_a_server_started_at_a_cache_size_the_tier_does_not_ship_is_a_fault(
    tmp_path: Path,
) -> None:
    sized = CACHE_ITEMS.replace('"0"', '"2048"')
    faults = check(copied(tmp_path, [(SUBAGENTS, CACHE_ITEMS, sized)])).faults
    assert [fault.service for fault in faults] == ["llama-subagent"]
    assert "where the tier requires '0'" in faults[0].detail


def test_a_server_started_at_a_budget_the_tier_does_not_ship_is_a_fault(tmp_path: Path) -> None:
    budgeted = BUDGET_ITEMS.replace('"0"', '"128"')
    faults = check(copied(tmp_path, [(ROSTER, BUDGET_ITEMS, budgeted)])).faults
    assert [fault.service for fault in faults] == ["llama-subagent-qwen"]
    assert "where the tier requires '0'" in faults[0].detail


def test_a_server_started_without_the_tool_capable_template_is_a_fault(tmp_path: Path) -> None:
    faults = check(copied(tmp_path, [(SUBAGENTS, JINJA_ITEM, "")])).faults
    assert [fault.detail.split(":")[0] for fault in faults] == ["the tool-capable chat template"]


def test_a_server_no_registry_names_is_held_the_day_its_override_is_written(tmp_path: Path) -> None:
    root = copied(tmp_path)
    (root / "docker" / "docker-compose.subagents-third.yml").write_text(THIRD, encoding="utf-8")
    faults = check(root).faults
    assert {fault.service for fault in faults} == {"llama-subagent-third"}
    assert len(faults) == sum(len(requirement.flags) for requirement in REQUIREMENTS)


def test_a_cpu_server_in_a_third_file_is_held_to_having_a_thread_count(tmp_path: Path) -> None:
    root = copied(tmp_path)
    correct = THIRD + JINJA_ITEM + KWARG_ITEMS + BUDGET_ITEMS + CACHE_ITEMS
    (root / "docker" / "docker-compose.subagents-third.yml").write_text(correct, encoding="utf-8")
    faults = check(root).faults
    assert [fault.service for fault in faults] == ["llama-subagent-third"]
    assert faults[0].detail.startswith("a thread count on a server that offloads no layer:")
    assert "it has no --threads" in faults[0].detail


@pytest.mark.parametrize("compose", [SUBAGENTS, ROSTER])
def test_a_shipped_cpu_server_losing_its_thread_count_is_a_fault(
    tmp_path: Path, compose: str
) -> None:
    faults = check(copied(tmp_path, [(compose, THREADS_ITEMS, "")])).faults
    assert [fault.file for fault in faults] == [f"docker/{compose}"]
    assert "it has no --threads" in faults[0].detail


def test_a_server_offloading_its_layers_is_asked_for_no_thread_count(tmp_path: Path) -> None:
    edits = [
        (SUBAGENTS, NGL_ITEMS, '      - "-ngl"\n      - "99"\n'),
        (SUBAGENTS, THREADS_ITEMS, ""),
    ]
    assert check(copied(tmp_path, edits)).faults == []


def test_an_artifact_named_in_the_family_is_one_a_membership_reader_can_classify() -> None:
    named = Artifact(file="f", where="w", line=1, variable="CORTEX_MODEL_FILE_ANYTHING")
    assert unclassifiable(named) is None


def test_an_artifact_named_outside_the_family_names_itself_and_says_what_it_costs() -> None:
    fault = unclassifiable(Artifact(file="f", where="w", line=1, variable="CORTEX_SUB_FILE"))
    assert fault is not None
    assert fault.detail.startswith("the artifact naming rule: ")
    assert "CORTEX_SUB_FILE" in fault.detail
    assert "drops out of the set unreported" in fault.detail


def test_a_hosted_tiers_artifact_written_another_way_is_reported_rather_than_dropped(
    tmp_path: Path,
) -> None:
    edits = [
        (TIER_MODULE, HOSTED_ALIAS, '"CORTEX_SUBAGENT_MODEL_FILE_GPU"'),
        (TIER_MODULE, HOSTED_TAIL, "                extra=(),\n"),
    ]
    scanned = check(copied(tmp_path, edits))
    assert scanned.servers == 2, "the tier really did leave the set, which is what is reported"
    assert [(fault.file, fault.service) for fault in scanned.faults] == [
        ((MODEL_MANAGER / TIER_MODULE).as_posix(), "subagent_gpu_file")
    ]


def test_a_compose_servers_artifact_written_another_way_is_reported_too(tmp_path: Path) -> None:
    faults = check(copied(tmp_path, [(SUBAGENTS, ARTIFACT_ITEM, MISSPELLED_ITEM)])).faults
    assert [(fault.file, fault.service) for fault in faults] == [
        (f"docker/{SUBAGENTS}", "llama-subagent")
    ]
    assert "CORTEX_SUBAGENT_MODEL_FILE" in faults[0].detail


def test_a_fourth_tier_arriving_under_a_name_no_reader_looks_at_is_held_the_day_it_is_added(
    tmp_path: Path,
) -> None:
    field = FOURTH_FIELD + (
        '    subagent_cpu_file: str = Field(\n        default="", '
        'validation_alias="CORTEX_SUBAGENT_MODEL_FILE_CPU"\n    )\n'
    )
    scanned = check(
        copied(
            tmp_path,
            [(TIER_MODULE, FOURTH_FIELD, field), (TIER_MODULE, FOURTH_TIER, FOURTH)],
        )
    )
    assert scanned.servers == 3, "the fourth tier is in no set, which is the fault"
    assert [fault.detail.split(":")[0] for fault in scanned.faults] == ["the artifact naming rule"]
    assert "CORTEX_SUBAGENT_MODEL_FILE_CPU" in scanned.faults[0].detail


def test_the_rule_runs_over_every_artifact_the_committed_tree_names(tmp_path: Path) -> None:
    assert check(copied(tmp_path)).artifacts >= 6


def test_a_tree_that_starts_no_subagent_server_either_way_is_reported_rather_than_passed(
    tmp_path: Path,
) -> None:
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.yml").write_text("services:\n  redis:\n", "utf-8")
    (tmp_path / MODEL_MANAGER).mkdir(parents=True)
    (tmp_path / MODEL_MANAGER / ARGV_MODULE).write_text(BARE_ARGV, encoding="utf-8")
    (tmp_path / MODEL_MANAGER / TIER_MODULE).write_text(BARE_TIERS, encoding="utf-8")
    with pytest.raises(FlagCheckError, match="a scan over nothing cannot fail"):
        check(tmp_path)


def test_a_sidecar_this_gate_cannot_read_leaves_by_the_gates_own_door(tmp_path: Path) -> None:
    root = copied(tmp_path)
    (root / MODEL_MANAGER / ARGV_MODULE).unlink()
    with pytest.raises(FlagCheckError, match=f"cannot read .*{ARGV_MODULE}"):
        check(root)


def test_a_rule_requiring_nothing_is_reported_rather_than_passed(tmp_path: Path) -> None:
    with pytest.raises(FlagCheckError, match="a rule over nothing cannot fail"):
        check(copied(tmp_path), requirements=(Requirement(label="", why="", flags=()),))


def test_a_compose_tree_that_cannot_be_read_leaves_by_the_gates_own_door(tmp_path: Path) -> None:
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.yml").write_text("services:\n  one: inline\n", "utf-8")
    with pytest.raises(FlagCheckError, match="inline service body"):
        check(tmp_path)


def test_a_tree_with_no_compose_file_at_all_is_an_input_failure(tmp_path: Path) -> None:
    with pytest.raises(FlagCheckError, match="no compose file"):
        check(tmp_path)


def test_the_cli_passes_over_the_committed_tree(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(REPO_ROOT)]) == 0
    printed = capsys.readouterr().out
    assert "flagcheck OK:" in printed
    assert "model artifact(s) this tree names" in printed, "both halves are reported, not one"


def test_the_cli_prints_every_fault_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = copied(tmp_path, [(SUBAGENTS, BUDGET_ITEMS, "")])
    assert main(["--root", str(root)]) == 1
    printed = capsys.readouterr()
    assert "llama-subagent: the tier's reasoning-off pair" in printed.out
    assert "1 problem(s)" in printed.err


def test_the_cli_reports_an_unreadable_tree_as_an_input_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(tmp_path)]) == 2
    assert "flagcheck: no compose file" in capsys.readouterr().err


def test_the_cli_refuses_a_root_that_is_not_a_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--root", str(tmp_path / "gone")]) == 2
    assert "is not a directory" in capsys.readouterr().err


def test_the_gate_defaults_to_the_registered_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    only = (Requirement(label="l", why="w", flags=(Flag("--nothing-carries-this"),)),)
    monkeypatch.setattr(flagcheck, "REQUIREMENTS", only)
    assert check_one(_server("--jinja")) == check_one(_server("--jinja"), only)
