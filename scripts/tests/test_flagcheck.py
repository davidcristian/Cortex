"""Behaviour of the gate holding every subagent server this repo starts to its tier's flags.

Three kinds of test sit below and the last two are the ones successive entries landed for. The
first mutates a server the tree already ships, taking one flag off it, which is the fault the
constant registry could already catch by naming that file. The second ADDS a server, in an
override nothing registered, which is the fault nothing could catch before the set was derived.
The third mutates the placement no compose file holds, the model host's own hosted subagent tier,
which the supervisor starts from an argv assembled in Python and which used to be correct by hand.

The last tests run the gate over the committed tree, where it is green or the fixtures are
testing the gate against itself.
"""

from collections.abc import Sequence
from pathlib import Path

import pytest

import flagcheck
from artifactnames import Artifact
from flagcheck import (
    REQUIREMENTS,
    Flag,
    FlagCheckError,
    Requirement,
    Server,
    check,
    check_one,
    main,
    missing,
    unclassifiable,
)
from hostedtiers import MODEL_MANAGER

REPO_ROOT = Path(__file__).resolve().parents[2]

SUBAGENTS = "docker-compose.subagents.yml"
ROSTER = "docker-compose.subagents-roster.yml"

# The sidecar's two halves: the module every tier's argv is assembled in, and the module the
# tiers themselves are declared in.
ARGV_MODULE = "tiers.py"
TIER_MODULE = "config.py"

# The reasoning-off pair as a compose command spells it, each half its own text so a test can
# take exactly one away, and the budget's own line so a test can retune it.
KWARG_ITEMS = '      - "--chat-template-kwargs"\n      - \'{"enable_thinking": false}\'\n'
BUDGET_ITEMS = '      - "--reasoning-budget"\n      - "0"\n'
JINJA_ITEM = '      - "--jinja"\n'

# The same pair and the same template where the sidecar spells them, which is what makes the two
# placements one rule's business rather than two.
HOSTED_PAIR = "                extra=_REASONING_OFF,\n"
HOSTED_JINJA = '_JINJA = "--jinja"'

# The two names the membership of that set is decided from, each where its own placement writes
# it: the alias the sidecar's subagent tier reads its artifact path under, and the item a compose
# command names its model file in. Either respelled is a member nothing would have missed.
HOSTED_ALIAS = '"CORTEX_MODEL_FILE_SUBAGENT_GPU"'
ARTIFACT_ITEM = '"/models/${CORTEX_MODEL_FILE_SUBAGENT:-'
MISSPELLED_ITEM = '"/models/${CORTEX_SUBAGENT_MODEL_FILE:-'

# A tier nobody registered: a fourth entry for a second subagent pick, with its own artifact
# setting and a tail its author forgot to copy.
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

# A sidecar hosting one tier that serves something other than subagents, which is what the floor
# under this gate needs: a tree readable at both placements and empty at both.
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

# A server nobody registered: a new override that starts one and wires the brain to dial it, with
# a command carrying none of the three flags.
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
"""


def copied(root: Path, edits: Sequence[tuple[str, str, str]] = ()) -> Path:
    """The committed tree copied under ``root``, with each named edit applied to its file.

    Both placements are copied, the compose stack and the model host's own two modules, because
    the rule now runs over both. Copying the real files is what makes a mutation a test rather
    than a hand run: a server that moves house leaves this failing instead of quietly checking a
    stack nobody runs. An edit is a triple so one file can take more than one, which is what a
    tier arriving with its own setting needs.
    """
    (root / "docker").mkdir(parents=True, exist_ok=True)
    (root / MODEL_MANAGER).mkdir(parents=True, exist_ok=True)
    sidecar = [REPO_ROOT / MODEL_MANAGER / name for name in (ARGV_MODULE, TIER_MODULE)]
    for path in [*(REPO_ROOT / "docker").glob("docker-compose*.yml"), *sidecar]:
        text = path.read_text(encoding="utf-8")
        for _, was, now in [edit for edit in edits if edit[0] == path.name]:
            assert was in text, f"{path.name} no longer spells {was!r}, so this mutation edits it"
            text = text.replace(was, now, 1)
        under = MODEL_MANAGER if path.suffix == ".py" else Path("docker")
        (root / under / path.name).write_text(text, encoding="utf-8")
    return root


def _server(*command: str) -> Server:
    """One server with the argv a test hands it, which is all the rule ever looks at."""
    return Server(file="docker/docker-compose.made-up.yml", service="one", line=1, command=command)


# ── one flag against one argv ──────────────────────────────────────────────────


def test_a_flag_the_argv_does_not_carry_is_missing() -> None:
    assert (
        missing(("--jinja",), Flag("--reasoning-budget", "0")) == "it carries no --reasoning-budget"
    )


def test_a_flag_that_takes_no_value_is_satisfied_by_being_there() -> None:
    assert missing(("--jinja", "--port"), Flag("--jinja")) is None


def test_a_flag_followed_by_the_required_value_is_satisfied() -> None:
    assert missing(("--reasoning-budget", "0"), Flag("--reasoning-budget", "0")) is None


def test_a_flag_followed_by_another_value_names_what_it_found() -> None:
    wrong = missing(("--reasoning-budget", "128"), Flag("--reasoning-budget", "0"))
    assert wrong == "--reasoning-budget is followed by '128' where the tier requires '0'"


def test_a_flag_written_last_is_followed_by_nothing_rather_than_by_a_value() -> None:
    """An argv ending on a flag that takes a value is a server started with an unset one."""
    wrong = missing(("--jinja", "--reasoning-budget"), Flag("--reasoning-budget", "0"))
    assert wrong == "--reasoning-budget is followed by None where the tier requires '0'"


def test_every_occurrence_of_a_repeated_flag_is_held_and_not_only_the_first() -> None:
    """llama.cpp takes the last spelling, so a server whose first pair is right and whose second
    is not runs at the second, and a check stopping at the first would call it compliant."""
    repeated = ("--reasoning-budget", "0", "--reasoning-budget", "512")
    assert missing(repeated, Flag("--reasoning-budget", "0")) is not None


# ── one server against the tier's requirements ─────────────────────────────────


def test_a_server_carrying_every_required_flag_has_no_fault() -> None:
    argv = (
        "--jinja",
        "--chat-template-kwargs",
        '{"enable_thinking": false}',
        "--reasoning-budget",
        "0",
    )
    assert check_one(_server(*argv)) == []


def test_a_fault_carries_the_requirement_that_names_it_and_the_reason_it_exists() -> None:
    """A gate saying only that something differs leaves a reader to rediscover why it must not."""
    faults = check_one(_server("--jinja"))
    assert len(faults) == 2, faults
    assert all(fault.detail.startswith("the tier's reasoning-off pair:") for fault in faults)
    assert all("only symptom is a slow subagent" in fault.detail for fault in faults)
    assert {fault.service for fault in faults} == {"one"}


# ── the whole tree, mutated the way the defect would really arrive ─────────────


def test_the_committed_tree_is_green_so_every_red_below_is_the_mutation(tmp_path: Path) -> None:
    scanned = check(copied(tmp_path))
    assert scanned.faults == []
    assert scanned.servers >= 3, "two compose servers and the hosted tier, so two would be a miss"


def test_the_hosted_tier_is_held_by_the_same_rule_as_the_servers_compose_starts(
    tmp_path: Path,
) -> None:
    """The placement no compose file holds. Taking the pair off the sidecar's own tier reddens
    this gate rather than only the suite next to it, which is what one rule over two placements
    means: the fault names the module the argv is assembled in, not a service."""
    faults = check(copied(tmp_path, [(TIER_MODULE, HOSTED_PAIR, "                extra=(),\n")]))
    assert [fault.service for fault in faults.faults] == ["CORTEX_MODEL_FILE_SUBAGENT_GPU"] * 2
    assert {fault.file for fault in faults.faults} == {(MODEL_MANAGER / TIER_MODULE).as_posix()}
    assert all("reasoning-off pair" in fault.detail for fault in faults.faults)


def test_a_fourth_tier_for_a_second_pick_is_held_the_day_it_is_declared(tmp_path: Path) -> None:
    """The whole reason the sidecar joined the set. Its subagent tier was one position in a fixed
    tuple, so a fourth added for a second pick carried whatever its author copied and the suite
    pinning today's three went on passing for the three it names."""
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
    assert len(faults) == 2, "the shared argv still carries --jinja, so only the pair is missing"


def test_a_sidecar_renaming_the_tool_capable_template_reddens_its_own_tier(
    tmp_path: Path,
) -> None:
    """The flag names are compared rather than each trusted to its own tree, so the requirement
    is spelled twice and cannot drift: the compose servers still carry it and this one does not."""
    edit = (ARGV_MODULE, HOSTED_JINJA, '_JINJA = "--chat-template"')
    faults = check(copied(tmp_path, [edit])).faults
    assert [fault.service for fault in faults] == ["CORTEX_MODEL_FILE_SUBAGENT_GPU"]
    assert faults[0].detail.startswith("the tool-capable chat template:")


@pytest.mark.parametrize("compose", [SUBAGENTS, ROSTER])
@pytest.mark.parametrize(("half", "items"), [("kwarg", KWARG_ITEMS), ("budget", BUDGET_ITEMS)])
def test_a_server_started_with_half_the_reasoning_off_pair_is_a_fault(
    tmp_path: Path, compose: str, half: str, items: str
) -> None:
    """Either flag gone from either shipped server: the kwarg does not reach the constrained
    shape and the budget does, so a server with one of them still runs a trace nobody reads."""
    faults = check(copied(tmp_path, [(compose, items, "")])).faults
    assert len(faults) == 1, half
    assert faults[0].file == f"docker/{compose}"


def test_a_server_started_at_a_budget_the_tier_does_not_ship_is_a_fault(tmp_path: Path) -> None:
    """A zero retuned to a count is a tier that thinks briefly, which this pair refuses: a narrow
    subtask wants no thought rather than a short one."""
    budgeted = BUDGET_ITEMS.replace('"0"', '"128"')
    faults = check(copied(tmp_path, [(ROSTER, BUDGET_ITEMS, budgeted)])).faults
    assert [fault.service for fault in faults] == ["llama-subagent-qwen"]
    assert "where the tier requires '0'" in faults[0].detail


def test_a_server_started_without_the_tool_capable_template_is_a_fault(tmp_path: Path) -> None:
    faults = check(copied(tmp_path, [(SUBAGENTS, JINJA_ITEM, "")])).faults
    assert [fault.detail.split(":")[0] for fault in faults] == ["the tool-capable chat template"]


def test_a_server_no_registry_names_is_held_the_day_its_override_is_written(tmp_path: Path) -> None:
    """The whole reason this scan exists. A third server, in a file nothing here has heard of,
    dialled by a roster entry and started with none of the flags: every requirement reddens, and
    nobody had to add it to a list first."""
    root = copied(tmp_path)
    (root / "docker" / "docker-compose.subagents-third.yml").write_text(THIRD, encoding="utf-8")
    faults = check(root).faults
    assert {fault.service for fault in faults} == {"llama-subagent-third"}
    assert len(faults) == sum(len(requirement.flags) for requirement in REQUIREMENTS)


# ── the names the set itself is decided from ───────────────────────────────────


def test_an_artifact_named_in_the_family_is_one_a_membership_reader_can_classify() -> None:
    named = Artifact(file="f", where="w", line=1, variable="CORTEX_MODEL_FILE_ANYTHING")
    assert unclassifiable(named) is None


def test_an_artifact_named_outside_the_family_names_itself_and_says_what_it_costs() -> None:
    """A gate reporting only that a name differs would leave the reader to rediscover why the
    spelling is anything but cosmetic."""
    fault = unclassifiable(Artifact(file="f", where="w", line=1, variable="CORTEX_SUB_FILE"))
    assert fault is not None
    assert fault.detail.startswith("the artifact naming rule: ")
    assert "CORTEX_SUB_FILE" in fault.detail
    assert "leaves the set in silence" in fault.detail


def test_a_hosted_tiers_artifact_spelled_another_way_is_reported_rather_than_dropped(
    tmp_path: Path,
) -> None:
    """The whole reason this rule exists, on the placement that had no second reading at all.
    Before it, renaming the alias out of the family took the tier out of both sets and the gate
    went on passing over the two servers that were left, tail or no tail."""
    edits = [
        (TIER_MODULE, HOSTED_ALIAS, '"CORTEX_SUBAGENT_MODEL_FILE_GPU"'),
        (TIER_MODULE, HOSTED_PAIR, "                extra=(),\n"),
    ]
    scanned = check(copied(tmp_path, edits))
    assert scanned.servers == 2, "the tier really did leave the set, which is what is reported"
    assert [(fault.file, fault.service) for fault in scanned.faults] == [
        ((MODEL_MANAGER / TIER_MODULE).as_posix(), "subagent_gpu_file")
    ]


def test_a_compose_servers_artifact_spelled_another_way_is_reported_too(tmp_path: Path) -> None:
    """The compose side keeps its safety net, the wiring that dials the server, so this fault is
    the naming one alone; the net is what an override leaving the address to the host environment
    does not have, and the name is held either way."""
    faults = check(copied(tmp_path, [(SUBAGENTS, ARTIFACT_ITEM, MISSPELLED_ITEM)])).faults
    assert [(fault.file, fault.service) for fault in faults] == [
        (f"docker/{SUBAGENTS}", "llama-subagent")
    ]
    assert "CORTEX_SUBAGENT_MODEL_FILE" in faults[0].detail


def test_a_fourth_tier_arriving_under_a_name_no_reader_looks_at_is_held_the_day_it_lands(
    tmp_path: Path,
) -> None:
    """The two halves together. A fourth tier spelled inside the family reddens for the tail its
    author forgot; spelled outside it, the tail is nobody's business because the tier is in no
    set, and the name is what reports it."""
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
    """A count over one placement would be a rule the other could walk under, so the scan reports
    what it held: the two compose servers' artifacts, the CPU embedder's, and the sidecar's three
    tiers. The embedder joined the count when it joined the family, no argv being excused now."""
    assert check(copied(tmp_path)).artifacts >= 6


# ── the floors, since a scan over nothing would be green forever ───────────────


def test_a_tree_that_starts_no_subagent_server_either_way_is_reported_rather_than_passed(
    tmp_path: Path,
) -> None:
    """Both placements empty, since a floor over one of them would be a floor a tree could still
    walk under by moving the tier to the other."""
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.yml").write_text("services:\n  redis:\n", "utf-8")
    (tmp_path / MODEL_MANAGER).mkdir(parents=True)
    (tmp_path / MODEL_MANAGER / ARGV_MODULE).write_text(BARE_ARGV, encoding="utf-8")
    (tmp_path / MODEL_MANAGER / TIER_MODULE).write_text(BARE_TIERS, encoding="utf-8")
    with pytest.raises(FlagCheckError, match="a scan over nothing cannot fail"):
        check(tmp_path)


def test_a_sidecar_this_gate_cannot_read_leaves_by_the_gates_own_door(tmp_path: Path) -> None:
    """The second reader's refusal arrives as an input failure like the first one's, so a tier
    whose declaration moved is reported rather than quietly dropped from the set."""
    root = copied(tmp_path)
    (root / MODEL_MANAGER / ARGV_MODULE).unlink()
    with pytest.raises(FlagCheckError, match=f"cannot read .*{ARGV_MODULE}"):
        check(root)


def test_a_rule_requiring_nothing_is_reported_rather_than_passed(tmp_path: Path) -> None:
    with pytest.raises(FlagCheckError, match="a rule over nothing cannot fail"):
        check(copied(tmp_path), requirements=(Requirement(label="", why="", flags=()),))


def test_a_compose_tree_that_cannot_be_read_leaves_by_the_gates_own_door(tmp_path: Path) -> None:
    """A reader's refusal is an input failure here, not a server problem, so it exits 2."""
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.yml").write_text("services:\n  one: inline\n", "utf-8")
    with pytest.raises(FlagCheckError, match="inline service body"):
        check(tmp_path)


def test_a_tree_with_no_compose_file_at_all_is_an_input_failure(tmp_path: Path) -> None:
    with pytest.raises(FlagCheckError, match="no compose file"):
        check(tmp_path)


# ── the command line ───────────────────────────────────────────────────────────


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
    """`check` and `check_one` both fall back to the same registry, so a caller passing nothing
    and the CLI are asking one question."""
    only = (Requirement(label="l", why="w", flags=(Flag("--nothing-carries-this"),)),)
    monkeypatch.setattr(flagcheck, "REQUIREMENTS", only)
    assert check_one(_server("--jinja")) == check_one(_server("--jinja"), only)


# ── the registry itself, which is production code here ─────────────────────────


def test_every_requirement_says_what_it_is_and_why_every_server_must_carry_it() -> None:
    """The sentence is what a fault prints, so an entry without one is a gate that reports a
    difference and leaves the reader to rediscover the reason."""
    for requirement in REQUIREMENTS:
        assert requirement.label, requirement
        assert requirement.why, requirement
        assert requirement.flags, requirement
        assert all(flag.name.startswith("--") for flag in requirement.flags), requirement
