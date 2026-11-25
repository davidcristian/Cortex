"""Split a forget message into the part asking to forget and the clauses asking to keep."""

import re
from collections.abc import Iterator

from cortex_core import forget_forms as forms

EVERY = forms.words(forms.ALL)
_TOKEN = re.compile(r"[^\W_]+|[,;.!?:]")
_MARKS = frozenset(",;.!?:")
# Only a keep verb's own forms, since "guardian", "keepsake" or "mantenimiento" can name a fact.
KEEP = re.compile(
    r"keep(?:s|ing)?|kept|behalt\w*|behält|bleib\w*|garde[rz]?|conserv(?:e[rsz]?|ons|a[rs]?|en)"
    r"|guard(?:a[rs]?|e[ns]?)|mant[eé]n(?:er|ga[ns]?|l[oa]s?)?|p[ăa]str\w*"
)
# No word that can also mean minus or less, such as "moins", "menos" or "mai puțin".
EXCEPT = forms.words(forms.EXCEPT)
# Too common a word to open a keep clause alone, so only after a word for all: "all but".
_BUT = forms.words(forms.ALL_BUT)
NOT = forms.words(forms.NOT)
_LEAD = frozenset(
    {"but", "and", "yet", "do", "don", "is", "isn", "s", "aber", "und", "mais", "et", "pero", "dar"}
)
_NAMING = frozenset({"the", "a", "an", "my", "your", "our", "his", "her", "their", "its"})
AND = forms.words(forms.AND)
# Romanian "o" is a pronoun before a verb, as in "cartela o păstrez", so it starts no keep clause.
_LIST = AND - {"o"}
_CONTRAST = forms.words(forms.BUT)
FORGET = re.compile(
    r"forg[eo]t\w*|delet\w*|remov\w*|eras\w*|oubli\w*|effac\w*|vergiss\w*|vergess\w*"
    r"|l[oö]sch\w*|olvid\w*|borr[ae]\w*|uit\w*|[șş]terg\w*"
)


def clauses(query: str) -> list[list[str]]:
    """The lowercase words and values of ``query``, split at each clause mark."""
    found: list[list[str]] = [[]]
    for token in _TOKEN.findall(query.lower()):
        if token in _MARKS:
            found.append([])
        else:
            found[-1].append(token)
    return [clause for clause in found if clause]


def opens_keep(clause: list[str], at: int) -> bool:
    """Whether ``clause`` asks to keep from ``at``: a keep verb, except, all but, or a negation
    first, after a leading word, or anywhere in a clause holding a forget verb."""
    token = clause[at]
    if KEEP.fullmatch(token):
        return NOT.isdisjoint(clause[max(0, at - 2) : at])
    led = not at or clause[at - 1] in _LEAD
    if token not in NOT or not (led or any(FORGET.fullmatch(word) for word in clause)):
        return token in EXCEPT or (token in _BUT and at > 0 and clause[at - 1] in EVERY)
    # "my do not disturb code" or "the not so new shed" names a fact rather than asking to keep one.
    if not _NAMING.isdisjoint(clause[max(0, at - 2) : at]):
        return False
    return at + 1 == len(clause) or not KEEP.fullmatch(clause[at + 1])


def _negates(clause: list[str], at: int) -> bool:
    """Whether a negation at ``at``, after no leading word, stands beside a forget verb or ends
    ``clause``, as in ``lösch nicht``, ``nicht löschen`` or ``vergiss die Karte nicht``."""
    if clause[at] not in NOT or not at or clause[at - 1] in _LEAD:
        return False
    after = clause[at + 1] if at + 1 < len(clause) else ""
    return at + 1 == len(clause) or any(FORGET.fullmatch(word) for word in (clause[at - 1], after))


def keeping(clause: list[str]) -> list[bool]:
    """Whether each token of ``clause`` is inside a clause asking to keep. A keep verb, or a
    ``_negates`` negation with its forget verb, also keeps the words before it back to a forget
    verb, a word for but, or a word for and after a forget verb or just before it."""
    flags: list[bool] = []
    start, forgot = 0, False
    for at, token in enumerate(clause):
        if FORGET.fullmatch(token) and NOT.isdisjoint(clause[max(0, at - 2) : at]):
            start, forgot = at + 1, True
            flags.append(False)
            continue
        joins = token in _CONTRAST or (forgot and token in _LIST)
        start = at if joins else start
        opens = not (flags and flags[-1]) and opens_keep(clause, at)
        negates = _negates(clause, at)
        if opens and (negates or KEEP.fullmatch(token)):
            begin = at - 1 if at and clause[at - 1] in _LIST else start
            begin -= negates and begin > 0 and FORGET.fullmatch(clause[begin - 1]) is not None
            flags[begin:] = [True] * (at - begin)
        flags.append(opens or bool(flags and flags[-1]))
    return flags


def parts(query: str) -> tuple[list[str], list[str]]:
    """The tokens of ``query`` outside a clause asking to keep, and those inside one. A clause
    with no forget verb joins a keep clause that ends before it, as in ``keep the card, my gym``."""
    forget: list[str] = []
    keep: list[str] = []
    kept = False
    for clause in clauses(query):
        unforgot = not any(FORGET.fullmatch(token) for token in clause)
        joined = kept and unforgot
        flags = [True] * len(clause) if joined else keeping(clause)
        for token, inside in zip(clause, flags, strict=True):
            (keep if inside else forget).append(token)
        kept = flags[-1]
    return forget, keep


def after_kept(query: str, kept: frozenset[str]) -> list[str]:
    """The words of each clause of ``query`` with no forget verb after one holding a word of
    ``kept`` past its last forget verb, which may ask to keep them too."""
    found: list[str] = []
    joins = False
    for clause in clauses(query):
        verbs = [place for place, token in enumerate(clause) if FORGET.fullmatch(token)]
        if joins and not verbs:
            found.extend(clause)
            continue
        joins = not kept.isdisjoint(clause[max(verbs, default=-1) + 1 :])
    return found


def after_but(query: str) -> list[str]:
    """The words of ``query`` after a word for but that follows a forget verb, to the end of its
    clause, which may ask to keep the rows they name: none of a clause that then holds a forget
    verb or a keep clause, or adds a row, as in ``but the card too``."""
    found: list[str] = []
    forgot = False
    for clause in clauses(query):
        verbs = [at for at, token in enumerate(clause) if FORGET.fullmatch(token)]
        first = -1 if forgot else min(verbs, default=len(clause))
        buts = (at for at, token in enumerate(clause) if at > first and token in _CONTRAST)
        cut = next(buts, len(clause))
        forgot = forgot or bool(verbs)
        rest = clause[cut + 1 :]
        adds = rest[-2:] == ["as", "well"] or not _ADD.isdisjoint(rest)
        told = adds or any(keeping(clause)[cut:]) or any(at > cut for at in verbs)
        found.extend([] if told else rest)
    return found


# A word adding a row to a forget, as in "also my phone" or "my phone as well".
_ADD = forms.words(forms.ALSO)
_OWNER = forms.words(forms.OWNER)
# Only the words for and: a word for or between two rows asks for one of them, not both.
JOIN = _LIST & _LEAD


# A word placing a value in a row or naming whose row it is, as in "4242 on my card".
_PLACE = forms.words(forms.PLACE)
WHOSE = _OWNER | frozenset(
    {"your", "our", "el", "los", "las", "mi", "mis", "tu", "tus", "su", "ton", "ta", "tes"}
)
# A word saying which row the value is, as in "4242, that is my card" or "4242, only the card".
_WHICH = frozenset({"it", "that", "which", "this", "is", "was", "i", "mean"}) | forms.words(
    forms.ONLY
)


def _runs(query: str, value: str) -> Iterator[tuple[list[str], bool | None]]:
    """Each run of ``query`` after ``value``, to a clause mark or forget verb, and whether its
    clause holds a keep clause from where the run starts: ``None`` for the words before a keep
    clause that opens inside a run, less the words leading into it, which are a run of their own."""
    wanted = [token for token in _TOKEN.findall(value.lower()) if token not in _MARKS]
    split = clauses(query)
    held = any(value_end(clause, wanted) is not None for clause in split)
    seen = False
    for clause in split:
        start = 0 if seen else value_end(clause, wanted) if held else forget_end(clause)
        if start is None:
            continue
        seen = True
        verb = (at for at in range(start, len(clause)) if FORGET.fullmatch(clause[at]))
        end, flags = next(verb, len(clause)), keeping(clause)
        keep = next((at for at in range(start, end) if flags[at]), start)
        lead = next((at for at in range(keep, start, -1) if clause[at - 1] not in _LEAD), start)
        if lead > start:
            yield clause[start:lead], None
        yield clause[keep:end], any(flags[keep:])


def after_value(query: str, value: str, named: frozenset[str]) -> list[str]:
    """The words of ``query`` after ``value`` that may ask to keep the rows they name: of each run
    to a clause mark or forget verb, those from the first word no reader reads before a word of
    ``named``, or all before a negation; none of a run adding a row or holding a keep clause."""
    read = named | _PLACE | WHOSE | _WHICH | AND
    found: list[str] = []
    for run, keeps in _runs(query, value):
        last = max((at for at, word in enumerate(run) if word in named), default=0)
        told = keeps or run[-2:] == ["as", "well"] or not _ADD.isdisjoint(run)
        unread = (at for at in range(last) if run[at] not in read and not run[at].isdigit())
        negated = not NOT.isdisjoint(run[last + 1 :])
        found.extend([] if told else run[next(unread, 0 if negated else len(run)) :])
    return found


LIMIT, ADDITION, EXCEPTION, UNREAD = "limit", "addition", "exception", "unread"
_ONE = frozenset({"one", "ones"})


def _role(run: list[str], named: frozenset[str]) -> str:
    """What ``run`` asks for the rows it names: ``ADDITION`` with an adding word at an end or a
    word for and first, ``EXCEPTION`` after a word for but, else ``LIMIT``; ``UNREAD`` when a
    word between is none of ``named`` and none a reader of that role reads."""
    body = run[1:] if run[0] in AND | _CONTRAST else run
    tail = 2 if body[-2:] == ["as", "well"] else len(_ADD.intersection(body[-1:]))
    head = len(_ADD.intersection(body[:1]))
    adds = run[0] in AND or bool(head or tail)
    core = body[head : len(body) - tail]
    core = core[: len(core) - len(_ONE.intersection(core[-1:]))]
    excepts = run[0] in _CONTRAST and not adds
    read = named | WHOSE | AND | (frozenset[str]() if excepts else _PLACE | _WHICH)
    if not all(word in read or word.isdigit() for word in core):
        return UNREAD
    return ADDITION if adds else EXCEPTION if excepts else LIMIT


def beside(
    query: str, value: str, named: frozenset[str], minus: frozenset[str]
) -> dict[str, set[str]]:
    """The words of ``named`` in the runs of ``query`` after ``value``, by the ``_role`` of their
    run, ``UNREAD`` when a later run naming no row holds a word no reader reads: none of a run
    with a keep clause, a negation or a word of ``minus``, no limit or addition before a clause."""
    found: dict[str, set[str]] = {LIMIT: set(), ADDITION: set(), EXCEPTION: set(), UNREAD: set()}
    read = _PLACE | WHOSE | _WHICH | AND | _ADD
    for run, keeps in _runs(query, value):
        words = named.intersection(run)
        if words and not keeps and (NOT | minus).isdisjoint(run):
            role = _role(run, named)
            found[role] |= set() if keeps is None and role in (LIMIT, ADDITION) else words
        elif not words and not all(word in read or word.isdigit() for word in run):
            unread = found[LIMIT] | found[ADDITION] | found[EXCEPTION] | found[UNREAD]
            found = {LIMIT: set(), ADDITION: set(), EXCEPTION: set(), UNREAD: unread}
    return found


def kept_again(query: str, value: str, named: frozenset[str]) -> set[str]:
    """The words of ``named`` in a run of ``query`` after ``value`` whose ``_role`` is ``UNREAD``,
    past the last place the run holds ``value``: a ``value`` of words of ``named`` is one only
    just after its first place and a row's name later. None of a run with a keep clause or negation.
    """
    wanted = [token for token in _TOKEN.findall(value.lower()) if token not in _MARKS]
    size, naming = len(wanted), named.issuperset(wanted)
    found: set[str] = set()
    for later, (run, keeps) in enumerate(_runs(query, value)):
        ends = (
            at + size
            for at in range(len(run) - size + 1)
            if run[at : at + size] == wanted and not (naming and (at or later))
        )
        words = named.intersection(run[max(ends, default=0) :])
        if words and not keeps and NOT.isdisjoint(run) and _role(run, named) == UNREAD:
            found |= words
    return found


def before_value(query: str, value: str) -> list[str]:
    """The words of each clause of ``query`` before the last place it holds ``value``, which name
    the rows the message asks to forget, as ``the card`` of ``Forget the card 4242``."""
    wanted = [token for token in _TOKEN.findall(value.lower()) if token not in _MARKS]
    size, split = len(wanted), clauses(query)
    held = any(value_end(clause, wanted) is not None for clause in split)
    found: list[str] = []
    for clause in split:
        places = [at for at in range(len(clause) - size + 1) if clause[at : at + size] == wanted]
        found.extend(clause[: max(places, default=0) if held else forget_end(clause) or 0])
    return found


def forget_end(clause: list[str]) -> int | None:
    """The length of ``clause`` when it holds a forget verb, where a message lacking the value
    reads the value's place."""
    return len(clause) if any(FORGET.fullmatch(token) for token in clause) else None


def value_end(clause: list[str], value: list[str]) -> int | None:
    """The index just after the first place ``clause`` holds the tokens ``value``, if it does."""
    size = len(value)
    ends = (at + size for at in range(len(clause) - size + 1) if clause[at : at + size] == value)
    return next(ends, None)
