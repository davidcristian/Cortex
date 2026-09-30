"""Subagent roles: named kinds of subtask, each with the sentence that names its reply."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SubagentRole:
    """One kind of subtask: what the spawn spec tells the cortex, and what the subagent reads."""

    description: str
    instruction: str

    def applied(self, instruction: str) -> str:
        """``instruction`` with this role's sentence after it, or unchanged for ``NO_ROLE``."""
        return f"{instruction} {self.instruction}" if self.instruction else instruction


NO_ROLE = SubagentRole(description="", instruction="")


@dataclass(frozen=True, slots=True)
class SubagentRoles:
    """The roles a spawn may name, keyed by the name the spawn spec advertises."""

    entries: Mapping[str, SubagentRole] = field(default_factory=dict[str, SubagentRole])

    def __post_init__(self) -> None:
        for name, role in self.entries.items():
            if not name or not role.description.strip() or not role.instruction.strip():
                msg = f"SubagentRoles entry {name!r} needs a name, a description and an instruction"
                raise ValueError(msg)

    def resolve(self, requested: str) -> SubagentRole | None:
        """The named role, ``NO_ROLE`` for ``""``, or ``None`` for a name that is not an entry."""
        if not requested:
            return NO_ROLE
        return self.entries.get(requested)


NO_ROLES = SubagentRoles()

# The names are a proposal for the maintainer's pick, and nothing beyond this machine stores
# them yet, so renaming a role is an edit to its key here.
SHIPPED_ROLES = SubagentRoles(
    entries={
        "precis": SubagentRole(
            description="the whole text made shorter, keeping its figures, names and dates",
            instruction=(
                "Reply with a shorter version that keeps every figure, name and date and adds "
                "nothing the text does not state."
            ),
        ),
        "excerpt": SubagentRole(
            description=(
                "a list of every item of one kind the text states, each written exactly as the "
                "text writes it, for a subtask that asks for all of them rather than one fact"
            ),
            instruction=(
                "Reply with each item the subtask asks for, written exactly as the text you "
                "were given writes it, one per line, and nothing else."
            ),
        ),
        "answer": SubagentRole(
            description="the one fact a question asks for, as the text states it",
            instruction=(
                "Reply with only the fact the question asks for, as the text you were given "
                "states it, or say that the text does not state it."
            ),
        ),
    }
)
