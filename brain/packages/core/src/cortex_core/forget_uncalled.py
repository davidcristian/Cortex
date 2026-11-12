"""Close a reply to a forget that asks to keep a fact on a turn that made no forget call."""

from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME

UNCALLED_FORGET_NOTE = "\n\n(Nothing was deleted from memory in this turn: it made no forget call.)"
UNCALLED_FORGET_NOTES = {
    "fr": "\n\n(Rien n'a été supprimé de la mémoire ici : aucun appel d'oubli n'a été fait.)",
    "de": "\n\n(Hier wurde nichts aus dem Gedächtnis gelöscht: es gab keinen Aufruf zum "
    "Vergessen.)",
    "es": "\n\n(Aquí no se borró nada de la memoria: no se hizo ninguna llamada de olvido.)",
    "ro": "\n\n(Nu s-a șters nimic din memorie aici: nu s-a făcut niciun apel de uitare.)",
}
_FORGET_TOOLS = frozenset({FORGET_CHOSEN_TOOL_NAME, FORGET_UNTRUSTED_TOOL_NAME})


def uncalled_note_due(query: str, runs: Sequence[ToolRun]) -> bool:
    """Whether ``query`` asks to forget beside a keep clause and no run of ``runs`` is a forget."""
    return asks_to_forget_keeping(query) and all(run.name not in _FORGET_TOOLS for run in runs)
