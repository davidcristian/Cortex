"""Paired draws of a text a model reads, in its old and its new wording, and how a row is read."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

type Side = Literal["old", "new"]
OLD: Side = "old"
NEW: Side = "new"
SIDES: tuple[Side, Side] = (OLD, NEW)


class WordingError(Exception):
    """A text holds neither form of a clause, or holds one more than once."""


@dataclass(frozen=True, slots=True)
class Wording:
    """One clause of a shipped text, in the form it had and the form proposed for it."""

    old: str
    new: str

    def render(self, text: str, side: Side) -> str:
        """Return ``text`` with this clause in the form ``side`` names, whichever form it holds."""
        held = [clause for clause in (self.old, self.new) if clause in text]
        if len(held) != 1 or text.count(held[0]) != 1:
            msg = f"expected exactly one of {self.old!r} or {self.new!r}, once"
            raise WordingError(msg)
        return text.replace(held[0], self.old if side == OLD else self.new)


def order(draw: int) -> tuple[Side, Side]:
    """The two sides in the order one draw posts them, the old one first on even draws."""
    return (OLD, NEW) if draw % 2 == 0 else (NEW, OLD)


def holds(old: int, new: int, slack: int, *, fewer_is_better: bool) -> bool:
    """Whether the new count is no worse than the old one by more than ``slack``."""
    return new <= old + slack if fewer_is_better else new >= old - slack


def fits(estimate_s: float, now: float, deadline: float | None) -> bool:
    """Whether a row priced at ``estimate_s`` ends by ``deadline``, when there is one."""
    return deadline is None or now + estimate_s <= deadline


@dataclass(frozen=True, slots=True)
class Batch:
    """What one reply did with the spawn tool: whether it called it, and each subtask's model."""

    delegated: bool
    picks: tuple[str, ...] = ()
    keyed: bool = False

    @property
    def spread(self) -> bool:
        """Whether the batch put its subtasks on at least two models."""
        return len(set(self.picks)) > 1


def read_batch(calls: Sequence[Mapping[str, object]], tool: str, default: str) -> Batch:
    """Read the first call to ``tool`` in an OpenAI ``tool_calls`` list, or no delegation."""
    for call in calls:
        function = cast("Mapping[str, object]", call.get("function") or {})
        if function.get("name") != tool:
            continue
        try:
            arguments: object = json.loads(str(function.get("arguments") or ""))
        except json.JSONDecodeError:
            return Batch(delegated=True)
        items: object = (
            cast("Mapping[str, object]", arguments).get("instructions")
            if isinstance(arguments, Mapping)
            else None
        )
        if not isinstance(items, list):
            return Batch(delegated=True)
        entries = cast("list[object]", items)
        chosen = [_chosen(entry) for entry in entries]
        return Batch(
            delegated=True,
            picks=tuple(name or default for name in chosen),
            keyed=any(chosen),
        )
    return Batch(delegated=False)


def _chosen(entry: object) -> str:
    """The model one instructions item names, or ``""`` when it names none."""
    if not isinstance(entry, Mapping):
        return ""
    model = cast("Mapping[str, object]", entry).get("model")
    return model if isinstance(model, str) else ""
