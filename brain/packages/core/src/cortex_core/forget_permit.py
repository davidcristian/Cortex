"""Find the stored rows a forget message permits a call to list, read without the call's text."""

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace

from cortex_core import forget_forms as forms
from cortex_core.forget_clauses import (
    AND,
    EVERY,
    FORGET,
    LIMIT,
    NOT,
    WHICH,
    WHOSE,
    beside,
    clauses,
    keeping,
    kept_again,
    parts,
)
from cortex_core.forget_inside import bounded, content, may_keep, request
from cortex_core.forget_keep_named import forget_named, forget_words
from cortex_core.forget_kinds import MINUS, extends, grows, names, prefixes, shorter, verbed
from cortex_core.forget_results import ALREADY_DELETED, FORGET_CHOSEN_LIMIT, NONE_FOUND
from cortex_core.forget_unnamed import TOPIC, just_said
from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_word, whole_values
from cortex_core.ports import MemoryStore
from cortex_core.scope import MemoryScope
from cortex_core.tools import ToolCall

Listing = Callable[[ToolCall], Awaitable[tuple[str, ...] | str]]
_PLACE = forms.words(forms.PLACE)
_READ = WHOSE | _PLACE | AND | WHICH
_TOKEN = re.compile(r"[^\W_]+")
_REPLY = "\nAssistant: "
# Clauses joined behind a forget verb read as the runs after a value, from their first word.
_VERB = "forget"


def call_text(call: ToolCall) -> str:
    """The text the call names, stripped; empty when the argument is missing or not a string."""
    value = call.arguments.get("text")
    return value.strip() if isinstance(value, str) else ""


def _digit(text: str) -> bool:
    """Whether ``text`` holds a digit."""
    return any(char.isdigit() for char in text)


def _same_fact(
    call: ToolCall, told: Sequence[MemoryRecord], seen: Sequence[MemoryRecord], *, apart: bool
) -> frozenset[str] | None:
    """The ids a message permits a call text holding a digit, or one ``apart`` from it, to list:
    the rows ``told`` it names and each of ``seen`` holding a whole value of one, as a recall does.
    ``None`` when it names no row, or holds a digit and the call's values are not ``apart``."""
    if not told or (_digit(call.stamp.query) and not apart):
        return None
    values = {key for row in told for key in whole_values(row.text)}
    shared = {row.id for row in seen if not values.isdisjoint(whole_values(row.text))}
    return frozenset(shared | {row.id for row in told})


def _asked(row: MemoryRecord) -> set[str]:
    """The lowercase words of the request of ``row``."""
    return set(_TOKEN.findall(row.text.split(_REPLY, 1)[0].lower()))


def _every(query: str, forget: list[str]) -> bool:
    """Whether a word for all of the words ``forget`` asks for every row: it ends a clause of
    ``query`` or is before a word for and, so a word after it, as in ``every code``, is no limit."""
    return any(
        token in EVERY and token in forget and clause[at + 1 : at + 2] in ([], *([w] for w in AND))
        for clause in clauses(query)
        for at, token in enumerate(clause)
    )


async def _coded(
    store: MemoryStore,
    scope: MemoryScope,
    call: ToolCall,
    told: Sequence[MemoryRecord],
    seen: Sequence[MemoryRecord],
    *,
    apart: bool,
) -> frozenset[str] | None:
    """The ids a message naming no row of ``told`` nor ``_every`` row permits: each row whose
    request holds a code word it asks to forget, or one such a word ``extends`` or ``grows`` from,
    and for a text holding a digit the row ``just_said`` reads. ``None`` if none does or both do."""
    tokens = parts(call.stamp.query)[0]
    codes = {token for token in tokens if code_word(token)}
    valued = _digit(call_text(call))
    if (
        told
        or _every(call.stamp.query, tokens)
        or (valued and _digit(call.stamp.query) and not apart)
    ):
        return None
    scopes = scope.read_scopes(call.stamp.session_id)
    rows = list(seen)
    for word in sorted(codes):
        rows += await store.find_text(word, limit=FORGET_CHOSEN_LIMIT + 1, scopes=scopes)
    unread = {
        code
        for code in codes & verbed(call.stamp.query)
        if all(code not in _asked(row) for row in rows)
    }
    grown = {token for token in verbed(call.stamp.query) & set(tokens) if not code_word(token)}
    starts = {stem for code in unread for stem in shorter(code)}
    for word in sorted(starts | {stem for token in grown for stem in prefixes(token)}):
        rows += await store.find_text(word, limit=FORGET_CHOSEN_LIMIT + 1, scopes=scopes)
    asked = {row.id: _asked(row) for row in rows}
    held = {
        row
        for row, words in asked.items()
        if not codes.isdisjoint(words)
        or any(extends(code, words) for code in unread)
        or any(grows(token, set(filter(code_word, words))) for token in grown)
    }
    said = just_said(list(seen), call.stamp.session_id) if valued else None
    if not held:
        return None
    return frozenset(held if said is None else held | {said})


async def permitted(
    call: ToolCall, told: Sequence[MemoryRecord], listing: Listing, *, apart: bool = False
) -> frozenset[str] | None:
    """The ids of the rows the call's message permits a call to list: each ``listing`` lists for a
    value of the message, and each of ``told`` holding none that ``forget_words`` names and
    ``may_keep`` does not keep. ``None`` when no row holds such a value or a digit is not apart."""
    query, values = call.stamp.query, whole_values(call.stamp.query).values()
    if _digit(call_text(call)) and not apart:
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
    words = forget_words(query)
    for row in told:
        held = any(search.search(row.text) for search in searches)
        if row.id not in kept and names(words, request(row)) and not held:
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


def _apart(call: ToolCall) -> bool:
    """Whether a message that is no forget of ``everything`` holds a digit and shares no whole
    value with a call text holding one, or holds a whole value beside a text holding none."""
    text, query = call_text(call), call.stamp.query
    if not _digit(query) or everything(query) is not None:
        return False
    if not _digit(text):
        return bool(whole_values(query))
    return whole_values(text).keys().isdisjoint(whole_values(query))


async def _store_named(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, seen: Sequence[MemoryRecord]
) -> tuple[dict[str, set[str]], frozenset[str]]:
    """The ids of the rows, of ``seen`` or stored, each word of the call's message names, and the
    words that name one, with each code word of the message."""
    query, scopes = call.stamp.query, scope.read_scopes(call.stamp.session_id)
    rows: dict[str, set[str]] = {}
    for word in sorted(content(query)):
        found = await store.find_text(word, limit=FORGET_CHOSEN_LIMIT + 1, scopes=scopes)
        rows[word] = {row.id for row in (*seen, *found) if names({word}, request(row))}
    codes = {word for clause in clauses(query) for word in clause if code_word(word)}
    return rows, frozenset({word for word, ids in rows.items() if ids} | codes)


async def _beyond_every(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, seen: Sequence[MemoryRecord]
) -> frozenset[str] | None:
    """The ids a forget of ``everything`` permits when words after it name a stored row under a
    role no reader reads: each a read limit names and those words do not, so none with no limit.
    ``None`` when the call's message is no such forget."""
    query, place = call.stamp.query, everything(call.stamp.query)
    if place is None:
        return None
    rows, named = await _store_named(store, scope, call, seen)
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


def _forgets(clause: list[str]) -> bool:
    """Whether ``clause`` holds a forget verb outside a keep clause, as ``don't delete`` is not."""
    return any(
        FORGET.fullmatch(word) and not kept
        for word, kept in zip(clause, keeping(clause), strict=True)
    )


def _head_run(clause: list[str], named: frozenset[str], every: int | None) -> list[str]:
    """The words of ``clause`` after its word for all at ``every``, as ``of it the card stays`` of
    ``Forget all of it the card stays``, or else after its forget verb and an unread first word,
    with a word of ``named`` past it, no value, no topic word before one, no placing word next."""
    if every is not None:
        return clause[every + 1 :]
    start = next((at + 1 for at, word in enumerate(clause) if FORGET.fullmatch(word)), 0)
    rest = clause[start + (not TOPIC.isdisjoint(clause[start : start + 1])) :]
    first = next((at for at, word in enumerate(rest) if word in named), 0)
    if not first or any(char.isdigit() for char in "".join(clause)) or rest[0] in _READ:
        return []
    return [] if rest[1] in _PLACE or not TOPIC.isdisjoint(rest[:first]) else rest[1:]


async def _kept_later(
    store: MemoryStore, scope: MemoryScope, call: ToolCall, seen: Sequence[MemoryRecord]
) -> frozenset[str]:
    """The ids of the stored rows a run no reader reads names: in a clause after the first holding
    a forget verb outside a keep clause, or the first clause of a message with none, or the
    ``_head_run`` of that clause."""
    split = clauses(call.stamp.query)
    first = next((at for at, clause in enumerate(split) if _forgets(clause)), 0)
    rows, named = await _store_named(store, scope, call, seen)
    place = everything(" ".join(split[first])) if split else None
    head = _head_run(split[first], named, place and place[1]) if split else []
    if first + 1 >= len(split) and not head:
        return frozenset()
    later = ", ".join([_VERB, " ".join(head), *(" ".join(clause) for clause in split[first + 1 :])])
    return frozenset(row for word in kept_again(later, _VERB, named) for row in rows.get(word, ()))


async def message_rows(
    store: MemoryStore,
    scope: MemoryScope,
    call: ToolCall,
    seen: Sequence[MemoryRecord],
    listing: Listing,
) -> tuple[list[MemoryRecord], frozenset[str] | None]:
    """The rows ``forget_named`` reads from the call's message, and the ids the first of
    ``permitted``, ``_same_fact`` and ``_coded`` that reads it permits, none for a call ``_apart``
    from it no reader reads, less each row ``_beyond_every`` or ``_kept_later`` keeps."""
    told = await forget_named(store, scope, call, FORGET_CHOSEN_LIMIT + 1, seen)
    apart = _apart(call)
    allowed = await permitted(call, told, listing, apart=apart)
    if allowed is None and (apart or _digit(call_text(call))):
        allowed = _same_fact(call, told, seen, apart=apart)
    if allowed is None:
        allowed = await _coded(store, scope, call, told, seen, apart=apart)
    if allowed is None and apart:
        allowed = frozenset[str]()
    beyond = await _beyond_every(store, scope, call, seen)
    if beyond is None:
        kept = await _kept_later(store, scope, call, seen)
        if kept and allowed is None:
            allowed = frozenset(row.id for row in seen)
        return told, allowed if allowed is None else allowed - kept
    return told, beyond if allowed is None else allowed & beyond
