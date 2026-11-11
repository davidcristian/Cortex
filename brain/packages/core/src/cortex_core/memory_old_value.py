"""Close a reply saying a value was updated or noted while a stored row still holds the old one."""

import re

from cortex_core.errors import MemoryStoreError
from cortex_core.forget_languages import FUNCTION
from cortex_core.memory_claim import claims_kept
from cortex_core.memory_claim_other import claims_kept_other, stated
from cortex_core.memory_claim_update import claims_updated
from cortex_core.memory_values import joined
from cortex_core.note_language import in_language
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

OLD_VALUE_NOTE = (
    "\n\n(A remembered exchange still holds {value}, the value your message corrects, so a later "
    "chat can still recall it. Nothing was deleted from memory in this turn. If you want it gone, "
    "ask to forget it in a message of its own.)"
)
OLD_VALUE_NOTES = {
    "fr": "\n\n(Un échange mémorisé contient toujours {value}, la valeur que votre message "
    "corrige, donc une autre conversation peut encore la retrouver. Rien n'a été supprimé de la "
    "mémoire ici. Si vous voulez la retirer, demandez de l'oublier dans un message à part.)",
    "de": "\n\n(Eine gespeicherte Unterhaltung enthält noch {value}, den Wert, den Ihre "
    "Nachricht korrigiert, daher kann ein späterer Chat ihn noch abrufen. Hier wurde nichts aus "
    "dem Gedächtnis gelöscht. Wenn Sie ihn entfernen möchten, bitten Sie in einer eigenen "
    "Nachricht darum, ihn zu vergessen.)",
    "es": "\n\n(Un intercambio guardado todavía contiene {value}, el valor que tu mensaje "
    "corrige, así que otro chat todavía puede recuperarlo. Aquí no se borró nada de la memoria. "
    "Si quieres quitarlo, pide que se olvide en un mensaje aparte.)",
    "ro": "\n\n(Un schimb memorat conține încă {value}, valoarea pe care mesajul tău o "
    "corectează, așa că o altă conversație o mai poate găsi. Nu s-a șters nimic din memorie aici. "
    "Dacă vrei să fie ștearsă, cere să fie uitată într-un mesaj separat.)",
}

_LIMIT = 8
_PART = r"[^\W_](?:[\w'\u2019-]|[./](?=\w)|(?<=\d):(?=\d))*"
_WORDS = rf"{_PART}(?:\s+{_PART}){{0,3}}"
_NAMED = r"(?:\d+(?:[ ./:-]\d+)*|(?-i:[A-Z])[\w'\u2019-]*)"
_NAMED_VALUE = re.compile(_NAMED)
_END = r"\s*(?=[,.;:!?)]|$)"
# "from Berlin to Paris" names a route or a range unless a verb of change comes before it.
_CHANGE = (
    r"\b(?:chang(?:e[ds]?|ing)|updat(?:e[ds]?|ing)|correct(?:s|ed|ing)?|switch(?:e[ds]|ing)?"
    r"|mov(?:e[ds]?|ing)|edit(?:s|ed|ing)?)\b[^.!?\n]*?"
)
_OLD = re.compile(
    rf",\s*(?:not|pas|nicht)\s+({_WORDS}){_END}|,\s*(?:no|nu)\s+({_WORDS}){_END}"
    rf"|\b(?:instead\s+of|no\s+longer)\s+({_WORDS}){_END}"
    rf"|{_CHANGE}\bfrom\s+({_NAMED})\s+to\s|\breplace\s+({_NAMED})\s+with\s"
    rf"|(?<![\w'\u2019])({_NAMED})\s+(?:is|was)\s+(?:wrong|incorrect|outdated|out\s+of\s+date)\b",
    re.IGNORECASE | re.MULTILINE,
)
_FUNCTION = frozenset(word for words in FUNCTION.values() for word in words) | frozenset(
    re.findall(
        r"\w+",
        "the a an my your our his her their its it this that these those me you him them to at in "
        "on for with of if when all any one so too very much more less sure only just yet even "
        "really now anymore today here there",
    )
)
_SEPARATOR = re.compile(r"[ ./-]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_FR = r"(?:mis\s+[àa]\s+jour|modifi[ée]e?s?|corrig[ée]e?s?|remplac[ée]e?s?|chang[ée]e?s?)"
_DE = r"(?:aktualisiert|ge[äa]ndert|korrigiert|ersetzt)"
_ES = r"(?:actualizad|cambiad|corregid|reemplazad|sustituid)[oa]s?"
_RO = r"(?:actualizat|schimbat|corectat|[îi]nlocuit|modificat)[ăae]?"
_CHANGED = re.compile(
    rf"\bj['\u2019]ai\s+(?:bien\s+|d[ée]j[àa]\s+)?{_FR}|\b(?:est|a\s+[ée]t[ée])\s+{_FR}"
    rf"|\bich\s+habe\s+(?:[\w'\u2019]+\s+){{0,4}}?{_DE}\b|\b(?:wurde|ist)\s+(?:jetzt\s+)?{_DE}\b"
    rf"|\b(?:he|ha\s+sido)\s+{_ES}\b|\b(?:lo|la)\s+he\s+{_ES}\b"
    rf"|\bam\s+{_RO}\b|\ba\s+fost\s+{_RO}\b",
    re.IGNORECASE,
)


def claims_changed(reply: str) -> bool:
    """Whether ``reply`` says in English or one of four other languages that a value changed."""
    return claims_updated(reply) or any(
        stated(sentence, match)
        for sentence in _SENTENCE_END.split(reply)
        if not sentence.rstrip().endswith("?")
        for match in _CHANGED.finditer(sentence)
    )


def corrected_values(message: str) -> tuple[str, ...]:
    """The values ``message`` names as old or wrong, in the order it names them."""
    found: list[str] = []
    for sentence in _SENTENCE_END.split(message):
        if sentence.rstrip().endswith("?"):
            continue
        for match in _OLD.finditer(sentence):
            value = next(group for group in match.groups() if group is not None)
            # The note calls a stored row outdated, so only a number or a capitalized name counts.
            named = _NAMED_VALUE.fullmatch(value) is not None
            if named and value.lower() not in _FUNCTION and value not in found:
                found.append(value)
    return tuple(found)


def holds(text: str, value: str) -> bool:
    """Whether ``text`` holds ``value`` whole, its groups joined by any or no separator."""
    groups = (re.escape(group) for group in _SEPARATOR.split(value) if group)
    pattern = rf"(?<![^\W_])(?:{'[ ./-]?'.join(groups)})(?![^\W_])"
    return re.search(pattern, text, re.IGNORECASE) is not None


async def hold_old_value(
    caps: TurnCapabilities, taint: TaintLedger, *, query: str, reply: str, session_id: str
) -> None:
    """Set ``taint.old_value`` to a value ``query`` corrects that a stored row still holds."""
    claimed = claims_changed(reply) or claims_kept(reply) or claims_kept_other(reply)
    if caps.memory is None or taint.forget_deleted or not claimed:
        return
    for value in corrected_values(query):
        try:
            rows = await caps.memory.find_value(value, session_id=session_id, limit=_LIMIT)
        except MemoryStoreError:
            # The note states what a row holds, so a store that cannot be read gives no note.
            return
        for row in rows:
            corrected = {joined(old) for old in corrected_values(row.text)}
            if holds(row.text, value) and joined(value) not in corrected:
                taint.old_value = value
                return


def old_value_note(value: str, language: str) -> str:
    """The note naming the old ``value`` a remembered exchange still holds, in ``language``."""
    return in_language(OLD_VALUE_NOTE, OLD_VALUE_NOTES, language).format(value=value)
