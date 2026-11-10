"""Name the items a turn deleted when no scheduling call of the turn set anything in their place."""

from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.note_language import ENGLISH, in_language
from cortex_core.schedule_claim import SCHEDULING_TOOLS
from cortex_core.tools import ToolResult

CANCELLED_CHARS = 80

CANCELLED_NOTE = "\n\n(Deleted in this turn, with nothing scheduled in its place:"
CANCELLED_NOTES = {
    "fr": "\n\n(Ce qui suit a été supprimé ici, et rien n'a été programmé à la place :",
    "de": "\n\n(Folgendes wurde hier gelöscht, und nichts wurde an seiner Stelle geplant:",
    "es": "\n\n(Se eliminó aquí lo siguiente, y no se programó nada en su lugar:",
    "ro": "\n\n(Ce urmează a fost șters aici, și nu s-a programat nimic în locul său:",
}


def cancelled_after(result: ToolResult, held: tuple[str, ...]) -> tuple[str, ...]:
    """``held``, plus the stored text of the item a cancel's ``result`` says it deleted."""
    return (*held, result.cancelled) if result.cancelled else held


def _line(text: str) -> str:
    """``text`` on one line, cut to ``CANCELLED_CHARS``."""
    flat = " ".join(text.split())
    return flat if len(flat) <= CANCELLED_CHARS else flat[: CANCELLED_CHARS - 3] + "..."


def cancelled_notes(
    runs: Sequence[ToolRun], cancelled: Sequence[str], language: str = ENGLISH
) -> tuple[str, ...]:
    """The note naming each item in ``cancelled``, unless one of ``runs`` scheduled anything."""
    if not cancelled or any(run.ok and run.name in SCHEDULING_TOOLS for run in runs):
        return ()
    head = in_language(CANCELLED_NOTE, CANCELLED_NOTES, language)
    return ("\n".join([head, *(f"- {_line(text)}" for text in cancelled)]) + ")",)
