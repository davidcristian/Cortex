"""Keep the rows a forget by value reaches that the message names no word of; say what it forgot."""

import re
from collections.abc import Iterable, Mapping

from cortex_core.memory import MemoryRecord
from cortex_core.memory_values import code_stem, code_word, digit_runs, kind_word, whole_values
from cortex_core.note_language import ENGLISH, in_language, message_language

_WORD = re.compile(r"[^\W\d_]{3,}")
_REPLY = "\nAssistant: "
_PREFIX = re.compile(r"\AUser: |\nAssistant: ")
_COMMON = frozenset(
    _WORD.findall(
        "the and you your are for but not that this these those with from have has had was were "
        "all any can its our also what about please now just too out one forget delete remove "
        "erase memory"
    )
)
# The function words of each other language, read only in a message of that language, since an
# English fact can be named by "den", "son" or "care".
_FUNCTION = {
    language: frozenset(_WORD.findall(words))
    for language, words in {
        "fr": "les des une aux dans pour par avec sur sous chez que qui quoi dont mon ton son mes "
        "tes ses notre votre nos vos leur leurs celui celle ceux celles cela ceci cet cette ces "
        "est sont était ont mais aussi non pas plus moi toi lui elle nous vous eux elles ils "
        "oublie oubliez efface effacez supprime supprimez mémoire merci",
        "de": "der die das den dem des ein eine einen einem einer eines und oder aber für von vom "
        "mit aus bei beim zum zur auf über unter nach mein meine meinen meinem meiner meines dein "
        "deine deinen deinem deiner sein seine seinen seinem ihr ihre ihren ihrem ihrer unser "
        "unsere euer eure ist sind war hat habe haben hast auch nicht noch nur jetzt bitte ich "
        "mich mir dich dir sie ihn ihm uns euch wir was dass diese dieser dieses diesen diesem "
        "vergiss lösche entferne",
        "es": "los las del una uno unos unas que con por para sin sobre mis tus sus mío mía tuyo "
        "tuya suyo suya nuestro nuestra este esta esto estos estas ese esa eso esos esas también "
        "pero está son era fue tiene tengo hay favor ahora solo ella ellos ellas usted les nos "
        "olvida olvide borra borre elimina memoria",
        "ro": "sau dar pentru din despre cel cea cei cele lui ale mea meu mele mei tău tale său "
        "sale nostru noastră acest această acesta aceasta aceste acel acea aceea care este sunt "
        "era are acum doar încă tine mine noi voi lor îmi mie nici rog uită șterge ştergeţi "
        "sterge memorie",
    }.items()
}

_EVERY = frozenset(
    _WORD.findall("all every everywhere everything partout tout tous toutes überall alle todas")
)
_TOPIC = frozenset({"about", "else", "sur", "über", "sobre"})
_REST = _EVERY | frozenset({"rest", "reste", "others"})
_TOKEN = re.compile(r"[^\W_]+|[,;.!?:]")
_MARKS = frozenset(",;.!?:")
# Only a keep verb's own forms, since "guardian", "keepsake" or "mantenimiento" can name a fact.
_KEEP = re.compile(
    r"keep(?:s|ing)?|kept|behalt\w*|behält|bleib\w*|garde[rz]?|conserv(?:e[rsz]?|ons|a[rs]?|en)"
    r"|guard(?:a[rs]?|e[ns]?)|mant[eé]n(?:er|ga[ns]?|l[oa]s?)?|p[ăa]str\w*"
)
_NOT = frozenset({"not", "t", "never", "nicht", "nie", "pas", "ne", "jamais", "no", "nunca", "nu"})
_LEAD = frozenset(
    {"but", "and", "yet", "do", "don", "is", "isn", "s", "aber", "und", "mais", "et", "pero", "dar"}
)
_NAMING = frozenset({"the", "a", "an", "my", "your", "our", "his", "her", "their", "its"})
_FORGET = re.compile(
    r"forg[eo]t\w*|delet\w*|remov\w*|eras\w*|oubli\w*|effac\w*|vergiss\w*|vergess\w*"
    r"|l[oö]sch\w*|olvid\w*|borr[ae]\w*|uit\w*|[șş]terg\w*"
)

KEPT_LINE = "Kept, since your message names none of their words or asks to keep them:"
KEPT_ALL = (
    "nothing was forgotten: each remembered exchange holding that value is about something the "
    "user's message does not name or asks to keep, so each was kept"
)


KEPT_NOTE = (
    "\n\n(Still in memory, since your message names none of their words or asks to keep them:"
)
KEPT_NOTES = {
    "fr": "\n\n(Toujours en mémoire, car votre message demande de les garder ou ne nomme aucun "
    "de leurs mots :",
    "de": "\n\n(Noch gespeichert, weil Ihre Nachricht darum bittet, sie zu behalten, oder keines "
    "ihrer Wörter nennt:",
    "es": "\n\n(Todavía en memoria, porque tu mensaje pide guardarlos o no nombra ninguna de sus "
    "palabras:",
    "ro": "\n\n(Încă în memorie, pentru că mesajul tău cere să fie păstrate sau nu numește niciun "
    "cuvânt al lor:",
}
_TURNS = 32


def kept_note(kept: Iterable[str], language: str = ENGLISH) -> str:
    """The note closing a reply that names the rows a forget kept, in the note ``language``."""
    head = in_language(KEPT_NOTE, KEPT_NOTES, language)
    return "\n".join([head, *(f"- {line}" for line in kept)]) + ")"


class KeptRows:
    """The excerpts of the rows each turn's forget calls kept as unnamed, by turn and row id."""

    def __init__(self) -> None:
        self._turns: dict[str, dict[str, str]] = {}

    def keep(self, turn: str, rows: Mapping[str, str]) -> None:
        """Record ``rows``, row id to excerpt, as kept in ``turn``."""
        self._turns[turn] = {**self._turns.pop(turn, {}), **rows}
        while len(self._turns) > _TURNS:
            del self._turns[next(iter(self._turns))]

    def drop(self, turn: str, ids: Iterable[str]) -> None:
        """Drop the rows of ``ids`` a call of ``turn`` deleted."""
        for row_id in ids:
            self._turns.get(turn, {}).pop(row_id, None)

    def held(self, turn: str) -> tuple[str, ...]:
        """The excerpts of the rows kept in ``turn`` that no later call deleted."""
        return tuple(self._turns.get(turn, {}).values())


def _keys(text: str) -> set[str]:
    """The values ``text`` holds, codes and years alike, by their letters and digits."""
    return {*whole_values(text), *digit_runs(text)}


def _words(text: str, function: frozenset[str] = frozenset()) -> set[str]:
    """The words of ``text`` that can name a fact: three or more letters, no common or code word."""
    words = {word.lower() for word in _WORD.findall(text)}
    return {word for word in words - _COMMON - function - _EVERY if not code_word(word)}


def _stems(text: str) -> set[str]:
    """The stems of the compound code words of ``text``, such as ``fahrrad`` of ``Fahrradcode``."""
    return {stem for word in _WORD.findall(text) if (stem := code_stem(word)) is not None}


def _kinds(text: str) -> set[str]:
    """The code words of ``text`` naming one kind of value, such as ``pin`` or ``passcode``."""
    return {word.lower() for word in _WORD.findall(text) if kind_word(word)}


def row_words(text: str) -> set[str]:
    """The words of a stored exchange that can name a fact, with the stems of its compounds."""
    plain = _PREFIX.sub("\n", text)
    return _words(plain) | _stems(plain)


def _row_names(text: str) -> set[str]:
    """The words of a stored exchange a forget part or keep clause can name it by."""
    return row_words(text) | _kinds(_PREFIX.sub("\n", text))


def _named(rows: list[MemoryRecord], words: set[str], deleted: Iterable[str]) -> bool:
    """Whether a word of ``words`` names a fact of ``rows`` or ``deleted``."""
    held = (*(record.text for record in rows), *deleted)
    return any(not words.isdisjoint(row_words(text)) for text in held)


def _clauses(query: str) -> list[list[str]]:
    """The lowercase words and values of ``query``, split at each clause mark."""
    clauses: list[list[str]] = [[]]
    for token in _TOKEN.findall(query.lower()):
        if token in _MARKS:
            clauses.append([])
        else:
            clauses[-1].append(token)
    return [clause for clause in clauses if clause]


def _opens_keep(clause: list[str], at: int) -> bool:
    """Whether ``clause`` asks to keep from ``at``: a keep verb or a leading negation."""
    token = clause[at]
    if _KEEP.fullmatch(token):
        return _NOT.isdisjoint(clause[max(0, at - 2) : at])
    if token not in _NOT or (at and clause[at - 1] not in _LEAD):
        return False
    # "my do not disturb code" names a fact rather than asking to keep one.
    if at > 1 and clause[at - 2] in _NAMING:
        return False
    return at + 1 == len(clause) or not _KEEP.fullmatch(clause[at + 1])


def _parts(query: str) -> tuple[list[str], list[str]]:
    """The tokens of ``query`` outside a clause asking to keep, and those inside one."""
    forget: list[str] = []
    keep: list[str] = []
    for clause in _clauses(query):
        keeping = False
        for at, token in enumerate(clause):
            if _FORGET.fullmatch(token) and _NOT.isdisjoint(clause[max(0, at - 2) : at]):
                keeping = False
            elif not keeping:
                keeping = _opens_keep(clause, at)
            (keep if keeping else forget).append(token)
    return forget, keep


def _split(query: str) -> tuple[set[str], set[str], set[str] | None, bool]:
    """The words of ``query`` naming a fact to forget, those only of a clause asking to keep, the
    words naming the rows to delete when a clause asks to keep, and whether it has a compound.
    """
    forget_tokens, keep_tokens = _parts(query)
    forget, keep = " ".join(forget_tokens), " ".join(keep_tokens)
    function = _FUNCTION.get(message_language(query), frozenset())
    named = _words(forget, function) | _stems(forget)
    kept = _words(keep) | _stems(keep) | _kinds(keep)
    kept = {word for word in kept - named - _kinds(forget) if not _KEEP.fullmatch(word)}
    listed = (named or _kinds(forget)) if keep_tokens else None
    return named, kept, listed, bool(_stems(forget))


def asks_to_keep(text: str, query: str) -> bool:
    """Whether a clause of ``query`` asking to keep names a fact of the row ``text``, or all."""
    return not _REST.isdisjoint(_parts(query)[1]) or not _split(query)[1].isdisjoint(
        _row_names(text)
    )


def _quantifies(query: str) -> bool:
    """Whether a word for all in ``query`` asks for every row: within two words of a value."""
    clauses = _clauses(query)
    for index, clause in enumerate(clauses):
        if any(_KEEP.fullmatch(token) for token in clause):
            continue
        for at, token in enumerate(clause):
            if token not in _EVERY or (at + 1 < len(clause) and clause[at + 1] in _TOPIC):
                continue
            beside = [*clause[max(0, at - 2) : at], *clause[at + 1 : at + 3]]
            if len(clause) == 1 and index:
                beside = clauses[index - 1][-1:]
            if any(char.isdigit() for char in "".join(beside)):
                return True
    return False


def _just_said(rows: list[MemoryRecord], session_id: str | None) -> str | None:
    """The id of the newest of ``rows`` the chat ``session_id`` stored, if it stored one."""
    own = [record for record in rows if session_id is not None and record.session_id == session_id]
    return max(own, key=lambda record: record.at).id if own else None


def unnamed(
    records: Iterable[MemoryRecord],
    text: str,
    query: str,
    deleted: Iterable[str] = (),
    session_id: str | None = None,
) -> list[MemoryRecord]:
    """The ``records`` to keep: with a clause asking to keep, each no whole word outside it names
    or that it names; else each whose request holds a value of ``text`` and no word of ``query``,
    unless ``query`` asks for every row or names nothing and ``session_id`` stored the newest.
    """
    rows, deleted = list(records), list(deleted)
    words, keep, listed, compound = _split(query)
    if not query.strip():
        return []
    if listed is not None:
        # A clause asks to keep: delete only a row a whole word names, so a misread keeps it.
        return [
            record
            for record in rows
            if listed.isdisjoint(names := _row_names(record.text)) or not keep.isdisjoint(names)
        ]
    asked, values = _keys(query), _keys(text) - _keys(query) or _keys(text)
    named = compound or _named(rows, words, deleted)
    every = values <= asked and (not named or _quantifies(query))
    said = None if named else _just_said(rows, session_id)
    return [
        record
        for record in rows
        if not every
        and record.id != said
        and not values.isdisjoint(_keys(record.text.split(_REPLY, 1)[0]))
        and words.isdisjoint(row_words(record.text))
    ]


def forgot(removed: int, holding: int, kept: int) -> str:
    """What a delete that left no match forgot; ``holding`` rows hold its numbers, ``kept`` kept."""
    if kept:
        return (
            f"forgot {removed} remembered exchanges; {kept} other remembered exchanges hold the "
            "same value but none of the words of the user's message, so they were kept and the "
            "value is still remembered"
        )
    if not holding:
        return (
            f"forgot {removed} remembered exchanges; no remembered exchange contains that text now"
        )
    return (
        f"forgot {removed} remembered exchanges that contain that text, but {holding} other "
        "remembered exchanges still hold a number a deleted one held, so that number is still "
        "remembered; a forget of the number itself would remove them"
    )
