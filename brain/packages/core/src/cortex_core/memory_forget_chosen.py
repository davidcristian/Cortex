"""The ``forget_memories`` built-in: delete the remembered exchanges that contain a named text."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from cortex_core.errors import MemoryStoreError
from cortex_core.forget_inside import INSIDE_ALL, INSIDE_LINE, inside
from cortex_core.forget_keep_named import keep_named
from cortex_core.forget_longer import LONGER_ALL, beside, longer, longer_lines
from cortex_core.forget_results import (
    ALREADY_DELETED,
    FORGET_CHOSEN_LIMIT,
    FORGET_NOT_KEPT_NOTE,
    LEFT_OUT_LINE,
    NONE_FOUND,
    TOO_MANY,
    about_deleted,
    failed_during,
    outlasted,
    unavailable,
    unlisted,
)
from cortex_core.forget_unnamed import KEPT_ALL, KEPT_LINE, KeptRows, asks_to_keep, forgot, unnamed
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_runs, digit_runs, short_groups, whole_values
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

FORGET_CHOSEN_TOOL_NAME = "forget_memories"

_EXCERPT_CHARS = 60
_PENDING_CALLS = 32
_TOKEN = re.compile(r"[^\W_]+")
_WORD = re.compile(r"[^\W\d_]{4,}")


def _text(call: ToolCall) -> str:
    """The text the call names, stripped; empty when the argument is missing or not a string."""
    value = call.arguments.get("text")
    return value.strip() if isinstance(value, str) else ""


def _excerpt(record: MemoryRecord, text: str) -> str:
    """One line of ``record`` around the first place it contains ``text``."""
    flat = " ".join(record.text.split())
    start = max(flat.lower().find(" ".join(text.lower().split())) - _EXCERPT_CHARS, 0)
    end = start + 2 * _EXCERPT_CHARS + len(text)
    return ("..." if start else "") + flat[start:end] + ("..." if end < len(flat) else "")


def _values(records: Sequence[MemoryRecord]) -> dict[str, str]:
    """The whole values of ``records``, such as a code or a phone number, in order."""
    values: dict[str, str] = {}
    for record in records:
        for key, form in whole_values(record.text).items():
            values.setdefault(key, form)
    return values


def _repeats(record: MemoryRecord, key: str, words: set[str]) -> bool:
    """Whether ``record`` holds the whole value ``key``, not as a date, and a word of ``words``."""
    tokens = {token.lower() for token in _TOKEN.findall(record.text)}
    own = whole_values(record.text).get(key)
    held = own is not None and not short_groups(own, record.text)
    return held and (not words or not tokens.isdisjoint(words))


@dataclass(frozen=True)
class _Chosen:
    """The rows a card listed by id and text, whether rows holding a value stayed, the rows kept."""

    ids: tuple[str, ...]
    texts: tuple[str, ...]
    left_out: bool
    kept: frozenset[str] = frozenset()
    far: frozenset[str] = frozenset()


class ForgetChosenTool:
    """Built-in ``forget_memories``: find the memories holding a text, list them, delete them."""

    def __init__(self, store: MemoryStore, scope: MemoryScope) -> None:
        self._store = store
        self._scope = scope
        self._shown: dict[str, _Chosen | str] = {}
        self._deleted_turns: dict[str, tuple[str, ...]] = {}
        self._deleted_rows: dict[str, tuple[str, ...]] = {}
        self._kept = KeptRows()
        self._spared = KeptRows()
        self._inside = KeptRows()
        self._longer = KeptRows()

    @property
    def result_note(self) -> str:
        """The note the dispatcher ends every result of a call to this tool with, run or not."""
        return FORGET_NOT_KEPT_NOTE

    @property
    def spec(self) -> ToolSpec:
        """One argument: the literal text every memory to delete contains."""
        return ToolSpec(
            name=FORGET_CHOSEN_TOOL_NAME,
            description=(
                "Delete from memory every remembered exchange that contains a given text, so no "
                "later chat recalls it. Call it whenever the user asks you to forget, delete or "
                "remove something from your memory, and never say something was forgotten unless "
                "this tool reported it. Pass the value itself when you know it, such as the "
                "number. When you do not, pass one word from the request that names it, such as "
                '"passport", and never ask the user to type the value: the user sees every match '
                "before anything is deleted."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The value, or one word from the request that names it.",
                    }
                },
                "required": ["text"],
            },
            confirm_required=True,
            private_arguments=True,
        )

    async def _found(self, call: ToolCall) -> Sequence[MemoryRecord]:
        """The memories the calling session can recall that contain the call's text."""
        return await self._store.find_text(
            _text(call),
            limit=FORGET_CHOSEN_LIMIT + 1,
            scopes=self._scope.read_scopes(call.stamp.session_id),
        )

    async def _repeating(
        self, call: ToolCall, found: Sequence[MemoryRecord]
    ) -> list[tuple[MemoryRecord, str, str]]:
        """Other memories holding a value of ``found`` and a word of the call or the value named."""
        words = {word.lower() for word in _WORD.findall(_text(call))}
        named = whole_values(_text(call))
        seen = {record.id for record in found}
        extra: list[tuple[MemoryRecord, str, str]] = []
        held = {**named, **_values(found)}
        values = [(key, form) for key, form in held.items() if words or key in named]
        for key, form in values:
            for record in await self._store.find_value(
                key,
                limit=FORGET_CHOSEN_LIMIT + 1,
                scopes=self._scope.read_scopes(call.stamp.session_id),
            ):
                if record.id not in seen and _repeats(record, key, words):
                    seen.add(record.id)
                    extra.append((record, form, whole_values(record.text)[key]))
        return extra

    async def _holding(self, call: ToolCall) -> int:
        """How many remaining rows not asked to keep hold four or more digits a deleted row held."""
        deleted = self._deleted_rows.get(call.stamp.turn_id, ())
        runs = {key for text in deleted for key in code_runs(text)}
        holders: set[str] = set()
        for key in runs:
            for record in await self._store.find_value(
                key,
                limit=FORGET_CHOSEN_LIMIT + 1,
                scopes=self._scope.read_scopes(call.stamp.session_id),
            ):
                held = not runs.isdisjoint(digit_runs(record.text))
                if held and not asks_to_keep(record.text, call.stamp.query):
                    holders.add(record.id)
        return len(holders)

    async def card(self, call: ToolCall) -> str | None:
        """List the stored memories the delete will remove; ``None`` when it removes none."""
        shown, card = await self._choose(call)
        self._shown[call.id] = shown
        while len(self._shown) > _PENDING_CALLS:
            del self._shown[next(iter(self._shown))]
        return card

    async def _choose(self, call: ToolCall) -> tuple[_Chosen | str, str | None]:
        """The rows to delete and the card listing them, or why nothing will be and no card."""
        if not _text(call):
            return "nothing was forgotten: the call named no text", None
        try:
            matches = await self._found(call)
            inner = inside(matches, _text(call))
            found = [record for record in matches if record.id not in inner]
            small = len(matches) <= FORGET_CHOSEN_LIMIT
            extra = await self._repeating(call, found) if small else []
            # A row also holding the value whole, in other separators, is listed rather than kept.
            inner -= {record.id for record, _, _ in extra}
            within = [record for record in matches if record.id in inner]
            named = await keep_named(self._store, self._scope, call, FORGET_CHOSEN_LIMIT + 1)
        except MemoryStoreError as err:
            return unavailable(err), None
        if not small:
            return TOO_MANY, None
        if not matches and not extra:
            deleted = self._deleted_turns.get(call.stamp.turn_id, ())
            return (ALREADY_DELETED if about_deleted(_text(call), deleted) else NONE_FOUND), None
        left_out = len(found) + len(extra) > FORGET_CHOSEN_LIMIT
        rows = [*found, *(row for row, _, _ in extra)]
        deleted = self._deleted_rows.get(call.stamp.turn_id, ())
        kept = unnamed(rows, _text(call), call.stamp.query, deleted, call.stamp.session_id)
        held = {record.id for record in kept}
        far = [row for row in longer(rows, _text(call), call.stamp.query) if row.id not in held]
        spared = {row.id: _excerpt(row, _text(call)) for row in (*kept, *within, *far)}
        self._spared.keep(call.stamp.turn_id, {**named, **spared})
        skip = held | {row.id for row in far}
        found = [record for record in found if record.id not in skip]
        repeats = [] if left_out else [row for row in extra if row[0].id not in skip]
        if not found and not repeats:
            turn = call.stamp.turn_id
            self._kept.keep(turn, {row.id: spared[row.id] for row in kept})
            self._inside.keep(turn, {row.id: spared[row.id] for row in within})
            self._longer.keep(turn, {row.id: spared[row.id] for row in far})
            self._inside.drop(turn, self._kept.ids(turn) | self._longer.ids(turn))
            return (KEPT_ALL if kept else LONGER_ALL if far else INSIDE_ALL), None
        listed = [*found, *(record for record, _, _ in repeats)]
        lines = [f"- {_excerpt(record, _text(call))}" for record in found]
        for form in dict.fromkeys(form for _, form, _ in repeats):
            lines.append(f"Listed because they also hold {form}:")
            lines.extend(
                f"- {_excerpt(record, own)}" for record, held, own in repeats if held == form
            )
        if left_out:
            lines.append(LEFT_OUT_LINE)
        if kept:
            lines.extend([KEPT_LINE, *(f"- {_excerpt(record, _text(call))}" for record in kept)])
        if within:
            lines.extend([INSIDE_LINE, *(f"- {_excerpt(row, _text(call))}" for row in within)])
        lines.extend(longer_lines(_excerpt(row, _text(call)) for row in far))
        card = "\n".join(
            [f"Deletes for good, with no undo, these {len(listed)} remembered exchanges:", *lines]
        )
        chosen = _Chosen(
            tuple(record.id for record in listed),
            tuple(record.text for record in listed),
            left_out,
            frozenset(held),
            frozenset(row.id for row in far),
        )
        return chosen, card

    def _result(
        self, call: ToolCall, content: str, *, error: bool = True, holding: int | None = None
    ) -> ToolResult:
        """The call's result: ``content`` as one sentence."""
        return ToolResult(
            call_id=call.id,
            content=f"{content}.",
            is_error=error,
            trust=Trust.TRUSTED,
            matched_nothing=content == NONE_FOUND,
            numbers_left=None if holding is None else holding > 0,
            kept=self._kept.held(call.stamp.turn_id),
            spared=self._spared.held(call.stamp.turn_id),
            inside=self._inside.held(call.stamp.turn_id),
            longer=self._longer.held(call.stamp.turn_id),
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delete exactly the memories the card listed, then say whether any still match."""
        shown = self._shown.pop(call.id, None)
        if shown is None:
            return self._result(call, "nothing was forgotten: no card listed what to delete")
        if isinstance(shown, str):
            return self._result(call, shown, error=shown not in (NONE_FOUND, ALREADY_DELETED))
        removed = 0
        try:
            removed = await self._store.delete_ids(shown.ids)
            turn = call.stamp.turn_id
            for rows in (self._kept, self._spared, self._inside, self._longer):
                rows.drop(turn, shown.ids)
            for ledger, texts in (
                (self._deleted_turns, (*shown.texts, _text(call))),
                (self._deleted_rows, shown.texts),
            ):
                ledger[turn] = (*ledger.get(turn, ()), *texts)
                while len(ledger) > _PENDING_CALLS:
                    del ledger[next(iter(ledger))]
            now = await self._found(call)
            inner = inside(now, _text(call)) - shown.kept - shown.far
            left = [row for row in now if row.id not in inner | shown.kept | shown.far]
            holding = 0 if left or shown.left_out else await self._holding(call)
        except MemoryStoreError as err:
            return replace(self._result(call, failed_during(removed, err)), forgot=removed)
        if left:
            said = outlasted(removed, len(left))
        elif shown.left_out:
            said = unlisted(removed)
        elif shown.far:
            said = beside(removed, len(shown.far))
        else:
            said = forgot(removed, holding, len(shown.kept), len(inner))
        error = bool(left) or shown.left_out
        result = self._result(call, said, error=error, holding=None if error else holding)
        return replace(result, forgot=removed)
