"""Close a reply to a forget request on a turn in which no forget call ran."""

import re
from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.memory_request import asks_kept, asks_to_forget

UNCALLED_FORGET_NOTE = "\n\n(Nothing was deleted from memory in this turn: no forget call ran.)"
UNCALLED_FORGET_NOTES = {
    "fr": "\n\n(Rien n'a été supprimé de la mémoire ici : aucun appel d'oubli n'a été exécuté.)",
    "de": "\n\n(Hier wurde nichts aus dem Gedächtnis gelöscht: kein Aufruf zum Vergessen "
    "wurde ausgeführt.)",
    "es": "\n\n(Aquí no se borró nada de la memoria: no se ejecutó ninguna llamada de olvido.)",
    "ro": "\n\n(Nu s-a șters nimic din memorie aici: nu s-a executat niciun apel de uitare.)",
}
_FORGET_TOOLS = frozenset({FORGET_CHOSEN_TOOL_NAME, FORGET_UNTRUSTED_TOOL_NAME})
# Read only beside a request to remember, since "delete my 9am reminder" asks nothing of memory.
_DELETE = re.compile(
    r"(?:^\W*|[,;:]\s*|\b(?:and|but|so|then|please)\s+)(?:(?:please|also|just|then|now)\s+)*"
    r"(?:delete|remove|wipe|erase|clear|purge)\b",
    re.IGNORECASE,
)


def uncalled_note_due(query: str, runs: Sequence[ToolRun]) -> bool:
    """Whether ``query`` asks to forget and no run of ``runs``, the calls that ran, is a forget."""
    asked = (
        asks_to_forget(query)
        or asks_to_forget_keeping(query)
        or (asks_kept(query) and _DELETE.search(query) is not None)
    )
    return asked and all(run.name not in _FORGET_TOOLS for run in runs)
