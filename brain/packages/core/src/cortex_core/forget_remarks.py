"""Read a forget message less each remark, a clause that asks for nothing."""

from cortex_core import forget_forms as forms
from cortex_core.forget_clauses import AND, FORGET, JOIN, clauses, keeping, opens_keep, value_end

# A relative word after the value opens a remark about it, as in "4242 that I texted".
_RELATIVE = forms.words(forms.RELATIVE)
_ADD = forms.words(forms.ALSO)
_OWNER = forms.words(forms.OWNER)


def _item(words: list[str], named: frozenset[str]) -> bool:
    """Whether ``words`` name one row: a word for the or my, words of ``named``, a last ``one``."""
    words = words[:-1] if words[-1:] in (["one"], ["ones"]) else words
    return len(words) > 1 and words[0] in _OWNER and named.issuperset(words[1:])


def _adds(clause: list[str], named: frozenset[str]) -> bool:
    """Whether ``clause`` only adds rows: an adding word at one end, then one ``_item`` or a list
    of them joined by a word for and, as in ``the phone and the locker too``."""
    head = clause[0] in _ADD
    tail = 2 if clause[-2:] == ["as", "well"] else int(clause[-1] in _ADD)
    if not head and not tail:
        return False
    items: list[list[str]] = [[]]
    for word in clause[1:] if head else clause[:-tail]:
        if word in JOIN:
            items.append([])
        else:
            items[-1].append(word)
    return all(_item(item, named) for item in items)


def _asks(clause: list[str]) -> bool:
    """Whether ``clause`` holds a forget verb or a clause asking to keep."""
    return any(FORGET.fullmatch(word) or opens_keep(clause, at) for at, word in enumerate(clause))


def _cut(clause: list[str], value: list[str]) -> list[list[str]]:
    """``clause`` split before the first relative word after ``value``, when it holds both."""
    at = value_end(clause, value) or len(clause)
    cut = next((i for i in range(at, len(clause)) if clause[i] in _RELATIVE), None)
    return [clause] if cut is None else [clause[:cut], clause[cut:]]


def asking(query: str, value: str, named: frozenset[str] = frozenset()) -> str:
    """The words of ``query`` less each remark: a clause, or its words from a relative word after
    ``value``, holding no forget verb, keep clause or ``value``, unless it opens with ``and`` or
    only adds a row of words ``named`` to a clause that does not end asking to keep."""
    wanted = [token for clause in clauses(value) for token in clause]
    found: list[str] = []
    asked, keeps = True, False
    for piece in (piece for clause in clauses(query) for piece in _cut(clause, wanted)):
        joins = asked and piece[0] in AND
        adds = _adds(piece, named)
        asked = (
            joins or _asks(piece) or value_end(piece, wanted) is not None or (adds and not keeps)
        )
        keeps = keeps if adds else keeping(piece)[-1]
        found.extend(piece if asked else [])
    return " ".join(found)
