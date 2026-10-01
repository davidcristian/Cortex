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
    ],
)
def test_an_entry_missing_a_name_or_a_description_is_a_wiring_error(
    name: str, role: SubagentRole
) -> None:
    with pytest.raises(ValueError, match="needs a name and a description"):
        SubagentRoles(entries={name: role})


def test_an_entry_without_a_sentence_leaves_the_instruction_as_it_was() -> None:
    bare = SubagentRole(description="a short reply", instruction="")
    assert SubagentRoles(entries={"bare": bare}).resolve("bare") is bare
    assert bare.applied("name a color") == "name a color"


def test_the_excerpt_description_sets_a_list_against_the_one_fact_of_an_answer() -> None:
    excerpt = SHIPPED_ROLES.entries["excerpt"].description
    assert "every item of one kind" in excerpt
    assert "rather than one fact" in excerpt
    assert "the one fact" in SHIPPED_ROLES.entries["answer"].description


def test_only_the_answer_role_changes_the_instruction() -> None:
    assert sorted(SHIPPED_ROLES.entries) == ["answer", "excerpt", "precis"]
    for name in SHIPPED_ROLES.entries:
        role = SHIPPED_ROLES.resolve(name)
        assert role is not None
        assert (role.applied("go") == "go") == (name != "answer")
