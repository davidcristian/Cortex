"""Find the stored rows a forget message permits a call to list, read without the call's text."""

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace

from cortex_core import forget_forms as forms
from cortex_core.forget_clauses import (
    EVERY,
    FORGET,
    LIMIT,
    NOT,
    WHOSE,
    beside,
    clauses,
    kept_again,
    parts,
)
from cortex_core.forget_inside import bounded, content, may_keep, request
from cortex_core.forget_keep_named import forget_named
from cortex_core.forget_kinds import MINUS, names
from cortex_core.forget_results import ALREADY_DELETED, FORGET_CHOSEN_LIMIT, NONE_FOUND
from cortex_core.forget_unnamed import TOPIC, just_said
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_word, whole_values
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall

Listing = Callable[[ToolCall], Awaitable[tuple[str, ...] | str]]
_PLACE = forms.words(forms.PLACE)
_TOKEN = re.compile(r"[^\W_]+")
_REPLY = "\nAssistant: "


def call_text(call: ToolCall) -> str:
    """The text the call names, stripped; empty when the argument is missing or not a string."""
    value = call.arguments.get("text")
    return value.strip() if isinstance(value, str) else ""


def _digit(text: str) -> bool:
    """Whether ``text`` holds a digit."""
    return any(char.isdigit() for char in text)


def _same_fact(
    call: ToolCall, told: Sequence[MemoryRecord], seen: Sequence[MemoryRecord]
) -> frozenset[str] | None:
    """The ids a message holding no digit permits a call text holding one to list: the rows
    ``told`` it names and each of ``seen`` holding a whole value of one, as a recall of it does.
    ``None`` when it names no row or holds a digit."""
    if not told or _digit(call.stamp.query):
        return None
    values = {key for row in told for key in whole_values(row.text)}
    shared = {row.id for row in seen if not values.isdisjoint(whole_values(row.text))}
    return frozenset(shared | {row.id for row in told})


async def _coded(
    store: MemoryStore,
    scope: MemoryScope,
    call: ToolCall,
    told: Sequence[MemoryRecord],
    seen: Sequence[MemoryRecord],
) -> frozenset[str] | None:
    """The ids a message naming no row of ``told`` and no word for all permits a call to list: each
    row, stored or of ``seen``, whose request holds a code word it asks to forget, and for a call
    text holding a digit the row ``just_said`` reads. ``None`` if none does or both hold a digit."""
    tokens = parts(call.stamp.query)[0]
    codes = {token for token in tokens if code_word(token)}
    valued = _digit(call_text(call))
    if told or not EVERY.isdisjoint(tokens) or (valued and _digit(call.stamp.query)):
        return None
    scopes = scope.read_scopes(call.stamp.session_id)
    rows = list(seen)
    for word in sorted(codes):
        rows += await store.find_text(word, limit=FORGET_CHOSEN_LIMIT + 1, scopes=scopes)
    asked = {row.id: _TOKEN.findall(row.text.split(_REPLY, 1)[0].lower()) for row in rows}
    held = {row for row, words in asked.items() if not codes.isdisjoint(words)}
    said = just_said(list(seen), call.stamp.session_id) if valued else None
    if not held:
        return None
    return frozenset(held if said is None else held | {said})


async def permitted(
    call: ToolCall, told: Sequence[MemoryRecord], listing: Listing
) -> frozenset[str] | None:
    """The ids of the rows the call's message permits a call to list: each ``listing`` lists for a
    value of the message, and each of ``told`` holding none that ``may_keep`` does not keep.
    ``None`` when the call's text holds a digit or no stored row holds a value of the message."""
    query, values = call.stamp.query, whole_values(call.stamp.query).values()
    if _digit(call_text(call)):
        return None
    ids: set[str] = set()
    read = False
    for form in values:
        listed = await listing(replace(call, arguments={"text": form}))
        read = read or listed not in (NONE_FOUND, ALREADY_DELETED)
        ids.update(() if isinstance(listed, str) else listed)
    if not read:
        return None
    searches = [search for search in map(bounded, values) if search is not None]
    kept = {row.id for form in values for row in may_keep(told, (), query, form)}
    for row in told:
        if row.id not in kept and not any(search.search(row.text) for search in searches):
            ids.add(row.id)
    return frozenset(ids)


def everything(query: str) -> tuple[int, int] | None:
    """The clause of ``query`` and the place in it of the first word for all after a forget verb,
    with no negation before it, no value after it in the clause and no topic word next, unless
    that word ends the clause."""
    for index, clause in enumerate(clauses(query)):
        verb = next((at for at, token in enumerate(clause) if FORGET.fullmatch(token)), None)
        for at, token in enumerate(clause):
            rest = clause[at + 1 :]
            plain = verb is not None and verb < at and NOT.isdisjoint(clause[:at])
            valued = any(char.isdigit() for char in "".join(rest))
            topic = len(rest) > 1 and not TOPIC.isdisjoint(rest[:1])
            if plain and token in EVERY and not valued and not topic:
                return index, at
    return None


async def _beyond_every(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, seen: Sequence[MemoryRecord]
) -> frozenset[str] | None:
    """The ids a forget of ``everything`` permits when words after it name a stored row under a
    role no reader reads: each a read limit names and those words do not, so none with no limit.
    ``None`` when the call's message is no such forget."""
    query, place = call.stamp.query, everything(call.stamp.query)
    if place is None:
        return None
    scopes = scope.read_scopes(call.stamp.session_id)
    rows: dict[str, set[str]] = {}
    for word in sorted(content(query)):
        found = await store.find_text(word, limit=FORGET_CHOSEN_LIMIT + 1, scopes=scopes)
        rows[word] = {row.id for row in (*seen, *found) if names({word}, request(row))}
    codes = {word for clause in clauses(query) for word in clause if code_word(word)}
    named = frozenset({word for word, ids in rows.items() if ids} | codes)
    split, (index, at) = clauses(query), place
    every = split[index][at]
    # Words opening as a limit does, as in "all my card numbers", are left to the limit readers.
    if not (WHOSE | _PLACE | named).isdisjoint(split[index][at + 1 : at + 2]):
        split[index] = split[index][: at + 1]
    unread = kept_again(", ".join(" ".join(clause) for clause in split), every, named)
    if not unread:
        return None
    limit = beside(query, every, named, MINUS)[LIMIT]
    kept = {row for word in unread for row in rows.get(word, ())}
    return frozenset({row for word in limit for row in rows.get(word, ())} - kept)


async def message_rows(
    store: MemoryStore,
    scope: MemoryScope,
    call: ToolCall,
    seen: Sequence[MemoryRecord],
    listing: Listing,
) -> tuple[list[MemoryRecord], frozenset[str] | None]:
    """The rows ``forget_named`` reads from the call's message, and the ids it permits a call to
    list: for a call text holding a digit those of ``_same_fact``, else those of ``permitted``,
    or those of ``_coded`` when neither reads it, less each row a forget of everything keeps."""
    told = await forget_named(store, scope, call, FORGET_CHOSEN_LIMIT + 1, seen)
    allowed = await permitted(call, told, listing)
    if _digit(call_text(call)):
        allowed = _same_fact(call, told, seen)
    if allowed is None:
        allowed = await _coded(store, scope, call, told, seen)
    beyond = await _beyond_every(store, scope, call, seen)
    if beyond is None or allowed is None:
        return told, allowed if beyond is None else beyond
    return told, allowed & beyond
