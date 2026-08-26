"""Behaviour of the gate holding every subagent server this repo starts to its tier's flags.

Two kinds of test sit below and the second kind is the point of the entry this landed for. The
first mutates a server the tree already ships, taking one flag off it, which is the fault the
constant registry could already catch by naming that file. The second ADDS a server, in an
override nothing registered, which is the fault nothing here could catch before: the set is
derived, so a server arriving tomorrow is held the day it is written.

The last tests run the gate over the committed compose tree, where it is green or the fixtures
are testing the gate against itself.
"""

from pathlib import Path

import pytest

import flagcheck
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
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SUBAGENTS = "docker-compose.subagents.yml"
ROSTER = "docker-compose.subagents-roster.yml"

# The reasoning-off pair as a compose command spells it, each half its own text so a test can
# take exactly one away, and the budget's own line so a test can retune it.
KWARG_ITEMS = '      - "--chat-template-kwargs"\n      - \'{"enable_thinking": false}\'\n'
BUDGET_ITEMS = '      - "--reasoning-budget"\n      - "0"\n'
JINJA_ITEM = '      - "--jinja"\n'

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


def copied(root: Path, edits: dict[str, tuple[str, str]] | None = None) -> Path:
    """The committed compose tree copied under ``root``, with one edit per named file.

    Copying the real files is what makes a mutation a test rather than a hand run: a server that
    moves house leaves this failing instead of quietly checking a stack nobody runs.
    """
    (root / "docker").mkdir(parents=True, exist_ok=True)
    for path in (REPO_ROOT / "docker").glob("docker-compose*.yml"):
        text = path.read_text(encoding="utf-8")
        was, now = (edits or {}).get(path.name, ("", ""))
        if was:
            assert was in text, f"{path.name} no longer spells {was!r}, so this mutation edits it"
            text = text.replace(was, now, 1)
        (root / "docker" / path.name).write_text(text, encoding="utf-8")
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
    assert scanned.servers >= 2, "the tree ships two subagent servers, so one would be a miss"


@pytest.mark.parametrize("compose", [SUBAGENTS, ROSTER])
@pytest.mark.parametrize(("half", "items"), [("kwarg", KWARG_ITEMS), ("budget", BUDGET_ITEMS)])
def test_a_server_started_with_half_the_reasoning_off_pair_is_a_fault(
    tmp_path: Path, compose: str, half: str, items: str
) -> None:
    """Either flag gone from either shipped server: the kwarg does not reach the constrained
    shape and the budget does, so a server with one of them still runs a trace nobody reads."""
    faults = check(copied(tmp_path, {compose: (items, "")})).faults
    assert len(faults) == 1, half
    assert faults[0].file == f"docker/{compose}"


def test_a_server_started_at_a_budget_the_tier_does_not_ship_is_a_fault(tmp_path: Path) -> None:
    """A zero retuned to a count is a tier that thinks briefly, which this pair refuses: a narrow
    subtask wants no thought rather than a short one."""
    budgeted = BUDGET_ITEMS.replace('"0"', '"128"')
    faults = check(copied(tmp_path, {ROSTER: (BUDGET_ITEMS, budgeted)})).faults
    assert [fault.service for fault in faults] == ["llama-subagent-qwen"]
    assert "where the tier requires '0'" in faults[0].detail


def test_a_server_started_without_the_tool_capable_template_is_a_fault(tmp_path: Path) -> None:
    faults = check(copied(tmp_path, {SUBAGENTS: (JINJA_ITEM, "")})).faults
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


# ── the floors, since a scan over nothing would be green forever ───────────────


def test_a_tree_that_starts_no_subagent_server_is_reported_rather_than_passed(
    tmp_path: Path,
) -> None:
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.yml").write_text("services:\n  redis:\n", "utf-8")
    with pytest.raises(FlagCheckError, match="a scan over nothing cannot fail"):
        check(tmp_path)


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
    assert "flagcheck OK:" in capsys.readouterr().out


def test_the_cli_prints_every_fault_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = copied(tmp_path, {SUBAGENTS: (BUDGET_ITEMS, "")})
    assert main(["--root", str(root)]) == 1
    printed = capsys.readouterr()
    assert "llama-subagent: the tier's reasoning-off pair" in printed.out
    assert "1 server problem(s)" in printed.err


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
