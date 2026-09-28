import pytest

from cortex_core import NO_ROLE, NO_ROLES, SHIPPED_ROLES, SubagentRole, SubagentRoles

_BRIEF = SubagentRole(description="a short reply", instruction="Reply in one line.")


def test_an_empty_request_resolves_to_no_role() -> None:
    assert SubagentRoles(entries={"brief": _BRIEF}).resolve("") is NO_ROLE


def test_a_named_role_resolves_to_its_entry() -> None:
    assert SubagentRoles(entries={"brief": _BRIEF}).resolve("brief") is _BRIEF


def test_a_name_outside_the_entries_resolves_to_nothing() -> None:
    assert SubagentRoles(entries={"brief": _BRIEF}).resolve("ghost") is None
    assert NO_ROLES.resolve("brief") is None


def test_a_role_puts_its_sentence_after_the_instruction() -> None:
    assert _BRIEF.applied("name a color") == "name a color Reply in one line."


def test_no_role_leaves_the_instruction_as_it_was() -> None:
    assert NO_ROLE.applied("name a color") == "name a color"


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("", _BRIEF),
        ("brief", SubagentRole(description=" ", instruction="Reply in one line.")),
        ("brief", SubagentRole(description="a short reply", instruction="")),
    ],
)
def test_an_entry_missing_a_name_or_either_text_is_a_wiring_error(
    name: str, role: SubagentRole
) -> None:
    with pytest.raises(ValueError, match="needs a name, a description and an instruction"):
        SubagentRoles(entries={name: role})


def test_every_shipped_role_resolves_and_changes_the_instruction() -> None:
    assert SHIPPED_ROLES.entries
    for name in SHIPPED_ROLES.entries:
        role = SHIPPED_ROLES.resolve(name)
        assert role is not None
        assert role.applied("go") != "go"
