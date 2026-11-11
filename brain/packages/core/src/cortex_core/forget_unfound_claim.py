"""Close a reply after a forget of the turn found no remembered exchange holding its text."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.forget_claim import deleted_memory
from cortex_core.forget_unfound_other import says_not_stored_other
from cortex_core.numbers_left_claim import names_still_held

DECLINED_FORGET_NOTE = (
    "\n\n(A forget card for this message was declined, so the remembered exchanges it listed are "
    "still stored.)"
)
DECLINED_FORGET_NOTES = {
    "fr": "\n\n(Une carte d'oubli pour ce message a été refusée, donc les échanges mémorisés "
    "qu'elle listait sont toujours enregistrés.)",
    "de": "\n\n(Eine Karte zum Vergessen für diese Nachricht wurde abgelehnt, daher sind die "
    "Unterhaltungen, die sie aufgeführt hat, noch gespeichert.)",
    "es": "\n\n(Una tarjeta de olvido para este mensaje fue rechazada, así que los intercambios "
    "que mostraba siguen guardados.)",
    "ro": "\n\n(Un card de uitare pentru acest mesaj a fost refuzat, așa că schimburile memorate "
    "pe care le arăta sunt încă în memorie.)",
}
DELETED_UNFOUND_NOTE = (
    "\n\n(A forget call in this turn deleted remembered exchanges, and another call found no "
    "remembered exchange holding its text. What the reply above calls not stored or not found may "
    "be among the deleted exchanges, rather than never stored.)"
)
DELETED_UNFOUND_NOTES = {
    "fr": "\n\n(Un appel d'oubli a supprimé ici des échanges mémorisés, et un autre appel n'a "
    "trouvé aucun échange mémorisé contenant son texte. Ce que la réponse ci-dessus dit non "
    "enregistré ou introuvable peut faire partie des échanges supprimés, plutôt que n'avoir "
    "jamais été enregistré.)",
    "de": "\n\n(Ein Aufruf zum Vergessen hat hier gespeicherte Unterhaltungen gelöscht, und ein "
    "anderer Aufruf hat keine gespeicherte Unterhaltung mit seinem Text gefunden. Was die Antwort "
    "oben als nicht gespeichert oder nicht gefunden bezeichnet, kann unter den gelöschten "
    "Unterhaltungen sein, statt nie gespeichert worden zu sein.)",
    "es": "\n\n(Una llamada de olvido borró aquí intercambios guardados, y otra llamada no "
    "encontró ningún intercambio guardado con su texto. Lo que la respuesta de arriba llama no "
    "guardado o no encontrado puede estar entre los intercambios borrados, en vez de no haberse "
    "guardado nunca.)",
    "ro": "\n\n(Un apel de uitare a șters aici schimburi memorate, iar un alt apel nu a găsit "
    "niciun schimb memorat care să conțină textul său. Ce răspunsul de mai sus numește nememorat "
    "sau negăsit poate fi printre schimburile șterse, în loc să nu fi fost memorat niciodată.)",
}

UNMATCHED_FORGET_NOTE = (
    "\n\n(Nothing was deleted from memory in this turn. A forget call in it searched for an exact "
    "text that no remembered exchange contains, so any remembered exchange that states the same "
    "fact in other words is still stored.)"
)
UNMATCHED_FORGET_NOTES = {
    "fr": "\n\n(Rien n'a été supprimé de la mémoire ici. Un appel d'oubli a cherché un texte "
    "exact qu'aucun échange mémorisé ne contient, donc un échange mémorisé qui dit la même chose "
    "en d'autres mots est toujours enregistré.)",
    "de": "\n\n(Hier wurde nichts aus dem Gedächtnis gelöscht. Ein Aufruf zum Vergessen suchte "
    "nach einem genauen Text, den keine gespeicherte Unterhaltung enthält, daher ist eine "
    "gespeicherte Unterhaltung, die dasselbe mit anderen Worten sagt, noch gespeichert.)",
    "es": "\n\n(Aquí no se borró nada de la memoria. Una llamada de olvido buscó un texto "
    "exacto que ningún intercambio guardado contiene, así que un intercambio guardado que dice lo "
    "mismo con otras palabras sigue guardado.)",
    "ro": "\n\n(Nu s-a șters nimic din memorie aici. Un apel de uitare a căutat un text exact "
    "pe care niciun schimb memorat nu îl conține, așa că un schimb memorat care spune același "
    "lucru în alte cuvinte este încă în memorie.)",
}

# "No other records of it remain" says the delete held, unless the clause names finding or storing
# or the sentence says the person never told it.
_HELD = (
    r"(?:(?=[^.!?]*\byou\s+(?:never\s+(?:told|gave|mentioned|shared|said)"
    r"|(?:didn['\u2019]t|did\s+not)\s+(?:tell|give|mention|share|say))\b)"
    r"|(?=[^,;:.!?]*\b(?:found|stored|saved|had)\b)|(?![^,;:.!?]*\b(?:remain(?:s|ing)?|left"
    r"|exists?|(?:is|are)\s+kept|any\s*more|any\s+longer|no\s+longer)\b))"
)
_NOT_STORED = re.compile(
    r"\b(?:didn['\u2019]t|did\s+not|couldn['\u2019]t|could\s+not|can['\u2019]t|cannot)\s+"
    r"(?:find|locate|have(?!\s+to\b))\b"
    rf"|\bno\s+(?:other\s+)?(?:records?|memory|entry|entries)\s+of\b{_HELD}"
    r"|\b(?:wasn['\u2019]t|weren['\u2019]t|was\s+not|were\s+not|never\s+(?:been\s+)?)"
    r"\s*(?:stored|saved|remembered|kept|found)\b"
    r"|\bnot\s+(?:stored|saved|found)\b(?!(?:\s+\w+){0,4}\s+(?:any\s*more|any\s+longer)\b)",
    re.IGNORECASE,
)
# "your new phone number wasn't saved" reports a fact of this message, which a forget keeps out.
_NEW = re.compile(r"\bnew\b", re.IGNORECASE)
_CLAUSE_BREAK = re.compile(r"[,;:]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def says_not_stored(reply: str) -> bool:
    """Whether a statement in ``reply`` says something was not found, not stored or not saved."""
    return any(
        not sentence.rstrip().endswith("?")
        and _NEW.search(_CLAUSE_BREAK.split(sentence[: found.start()])[-1]) is None
        for sentence in _SENTENCE_END.split(reply)
        for found in _NOT_STORED.finditer(sentence)
    )


def declined_note_due(reply: str, *, declined: bool) -> bool:
    """Whether a ``declined`` forget card kept its rows and ``reply`` does not say they are held."""
    return declined and not names_still_held(reply)


def unfound_claim(runs: Sequence[ToolRun], reply: str, *, unmatched: int) -> bool:
    """Whether a forget among ``runs`` deleted rows, one matched nothing, and ``reply`` says so."""
    said = says_not_stored(reply) or says_not_stored_other(reply)
    return unmatched > 0 and deleted_memory(runs, unmatched) and said


def unmatched_note_due(runs: Sequence[ToolRun], *, unmatched: int, deleted: int) -> bool:
    """Whether a forget among ``runs`` matched nothing and no forget of the turn deleted a row.

    ``deleted`` counts the rows the turn's ``forget_memories`` calls removed, failed ones included.
    """
    return unmatched > 0 and not deleted and not deleted_memory(runs, unmatched)
