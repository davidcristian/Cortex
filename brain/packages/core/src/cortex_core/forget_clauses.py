"""Split a forget message into the part asking to forget and the clauses asking to keep."""

import re

_WORD = re.compile(r"[^\W\d_]{3,}")
EVERY = frozenset(
    _WORD.findall("all every everywhere everything partout tout tous toutes überall alle todas")
)
_TOKEN = re.compile(r"[^\W_]+|[,;.!?:]")
_MARKS = frozenset(",;.!?:")
# Only a keep verb's own forms, since "guardian", "keepsake" or "mantenimiento" can name a fact.
KEEP = re.compile(
    r"keep(?:s|ing)?|kept|behalt\w*|behält|bleib\w*|garde[rz]?|conserv(?:e[rsz]?|ons|a[rs]?|en)"
    r"|guard(?:a[rs]?|e[ns]?)|mant[eé]n(?:er|ga[ns]?|l[oa]s?)?|p[ăa]str\w*"
)
# No word that can also mean minus or less, such as "moins", "menos" or "mai puțin".
EXCEPT = frozenset(
    _WORD.findall("except excluding sauf hormis excepté außer ausgenommen excepto salvo exceptând")
)
# Too common a word to open a keep clause alone, so only after a word for all: "all but".
_BUT = frozenset({"but"})
NOT = frozenset({"not", "t", "never", "nicht", "nie", "pas", "ne", "jamais", "no", "nunca", "nu"})
_LEAD = frozenset(
    {"but", "and", "yet", "do", "don", "is", "isn", "s", "aber", "und", "mais", "et", "pero", "dar"}
)
_NAMING = frozenset({"the", "a", "an", "my", "your", "our", "his", "her", "their", "its"})
_AND = frozenset({"and", "or", "et", "ou", "und", "oder", "y", "o", "și", "şi", "sau"})
# Romanian "o" is a pronoun before a verb, as in "cartela o păstrez", so it starts no keep clause.
_JOIN = (_AND - {"o"}) | {"but", "yet", "aber", "mais", "pero", "dar"}
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


def _opens_keep(clause: list[str], at: int) -> bool:
    """Whether ``clause`` asks to keep from ``at``: a keep verb, except, all but, or a negation."""
    token = clause[at]
    if KEEP.fullmatch(token):
        return NOT.isdisjoint(clause[max(0, at - 2) : at])
    if token not in NOT or (at and clause[at - 1] not in _LEAD):
        return token in EXCEPT or (token in _BUT and at > 0 and clause[at - 1] in EVERY)
    # "my do not disturb code" names a fact rather than asking to keep one.
    if at > 1 and clause[at - 2] in _NAMING:
        return False
    return at + 1 == len(clause) or not KEEP.fullmatch(clause[at + 1])


def _keeping(clause: list[str]) -> list[bool]:
    """Whether each token of ``clause`` is inside a clause asking to keep. A keep verb also keeps
    the words before it back to a forget verb or a joining word, as in ``mein Handy bleibt``."""
    flags: list[bool] = []
    start = 0
    for at, token in enumerate(clause):
        if FORGET.fullmatch(token) and NOT.isdisjoint(clause[max(0, at - 2) : at]):
            start = at + 1
            flags.append(False)
            continue
        start = at if token in _JOIN else start
        opens = not (flags and flags[-1]) and _opens_keep(clause, at)
        if opens and KEEP.fullmatch(token):
            flags[start:] = [True] * (at - start)
        flags.append(opens or bool(flags and flags[-1]))
    return flags


def parts(query: str) -> tuple[list[str], list[str]]:
    """The tokens of ``query`` outside a clause asking to keep, and those inside one."""
    forget: list[str] = []
    keep: list[str] = []
    for clause in clauses(query):
        for token, keeping in zip(clause, _keeping(clause), strict=True):
            (keep if keeping else forget).append(token)
    return forget, keep


# A relative word after the value opens a remark about it, as in "4242 that I texted".
_RELATIVE = frozenset({"that", "which", "where", "que", "qu", "qui", "dont", "où", "donde", "care"})


# A word adding a row to a forget, as in "also my phone" or "my phone as well".
_ADD = frozenset({"too", "also", "plus", "aussi", "également", "auch", "ebenfalls"})
_OWNER = frozenset(
    {"the", "my", "le", "la", "les", "l", "mon", "ma", "mes", "der", "die", "das", "den", "mein"}
    | {"meine", "meinen"}
)


def _adds(clause: list[str], named: frozenset[str]) -> bool:
    """Whether ``clause`` only adds a row: an adding word at one end, then a word for the or my,
    words of ``named`` only and an optional ``one``."""
    head = clause[0] in _ADD
    tail = 2 if clause[-2:] == ["as", "well"] else int(clause[-1] in _ADD)
    if not head and not tail:
        return False
    body = clause[1:] if head else clause[:-tail]
    body = body[:-1] if body[-1:] in (["one"], ["ones"]) else body
    return len(body) > 1 and body[0] in _OWNER and named.issuperset(body[1:])


def _asks(clause: list[str]) -> bool:
    """Whether ``clause`` holds a forget verb or a clause asking to keep."""
    return any(FORGET.fullmatch(word) or _opens_keep(clause, at) for at, word in enumerate(clause))


def _after(clause: list[str], value: list[str]) -> int | None:
    """The index just after the first place ``clause`` holds the tokens ``value``, if it does."""
    size = len(value)
    ends = (at + size for at in range(len(clause) - size + 1) if clause[at : at + size] == value)
    return next(ends, None)


def _cut(clause: list[str], value: list[str]) -> list[list[str]]:
    """``clause`` split before the first relative word after ``value``, when it holds both."""
    at = _after(clause, value) or len(clause)
    cut = next((i for i in range(at, len(clause)) if clause[i] in _RELATIVE), None)
    return [clause] if cut is None else [clause[:cut], clause[cut:]]


def asking(query: str, value: str, named: frozenset[str] = frozenset()) -> str:
    """The words of ``query`` less each remark: a clause, or its words from a relative word after
    ``value``, holding no forget verb, keep clause or ``value``, unless it opens with ``and`` or
    only adds a row of words ``named`` to a clause that does not end asking to keep."""
    wanted = [token for token in _TOKEN.findall(value.lower()) if token not in _MARKS]
    found: list[str] = []
    asked, keeps = True, False
    for piece in (piece for clause in clauses(query) for piece in _cut(clause, wanted)):
        joins = asked and piece[0] in _AND
        adds = _adds(piece, named)
        asked = joins or _asks(piece) or _after(piece, wanted) is not None or (adds and not keeps)
        keeps = keeps if adds else _keeping(piece)[-1]
        found.extend(piece if asked else [])
    return " ".join(found)
