from subagentflags import REQUIREMENTS, Flag, Requirement, applies, missing


def test_a_flag_the_argv_does_not_carry_is_missing() -> None:
    assert missing(("--jinja",), Flag("--reasoning-budget", "0")) == "it has no --reasoning-budget"


def test_a_flag_that_takes_no_value_is_satisfied_by_being_there() -> None:
    assert missing(("--jinja", "--port"), Flag("--jinja")) is None


def test_a_flag_followed_by_the_required_value_is_satisfied() -> None:
    assert missing(("--reasoning-budget", "0"), Flag("--reasoning-budget", "0")) is None


def test_a_flag_followed_by_another_value_names_what_it_found() -> None:
    wrong = missing(("--reasoning-budget", "128"), Flag("--reasoning-budget", "0"))
    assert wrong == "--reasoning-budget is followed by '128' where the tier requires '0'"


def test_a_flag_written_last_is_followed_by_nothing_rather_than_by_a_value() -> None:
    wrong = missing(("--jinja", "--reasoning-budget"), Flag("--reasoning-budget", "0"))
    assert wrong == "--reasoning-budget is followed by None where the tier requires '0'"


def test_every_occurrence_of_a_repeated_flag_is_held_and_not_only_the_first() -> None:
    repeated = ("--reasoning-budget", "0", "--reasoning-budget", "512")
    assert missing(repeated, Flag("--reasoning-budget", "0")) is not None


def _requirement(when: Flag | None) -> Requirement:
    return Requirement(label="l", why="w", flags=(Flag("--threads"),), when=when)


def test_a_requirement_naming_no_argv_reaches_every_server() -> None:
    assert applies((), _requirement(None))


def test_a_requirement_naming_an_argv_reaches_the_server_that_carries_it() -> None:
    assert applies(("-ngl", "0"), _requirement(Flag("-ngl", "0")))


def test_a_requirement_naming_an_argv_passes_over_the_server_that_does_not() -> None:
    assert not applies(("-ngl", "99"), _requirement(Flag("-ngl", "0")))


def test_every_requirement_says_what_it_is_and_why_the_servers_it_reaches_must_carry_it() -> None:
    for requirement in REQUIREMENTS:
        assert requirement.label, requirement
        assert requirement.why, requirement
        assert requirement.flags, requirement
        assert all(flag.name.startswith("--") for flag in requirement.flags), requirement


def test_a_conditional_requirement_is_written_over_a_flag_a_server_really_writes() -> None:
    conditional = [requirement.when for requirement in REQUIREMENTS if requirement.when is not None]
    assert conditional, "the thread count is conditional, so at least one entry names an argv"
    assert all(when.name.startswith("-") and when.value for when in conditional)
