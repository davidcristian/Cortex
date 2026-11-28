"""Close a turn about a reminder when no schedule store is configured."""

from collections.abc import Sequence

from cortex_core.conversation import ToolRun
from cortex_core.note_language import in_language
from cortex_core.schedule_claim import unscheduled_claim_note
from cortex_core.unasked_tools import asks_reminder

REMINDERS_OFF_NOTE = "\n\n(Reminders are off here, so nothing in this turn was scheduled.)"
REMINDERS_OFF_NOTES = {
    "fr": "\n\n(Les rappels sont désactivés ici, donc rien n'a été programmé.)",
    "de": "\n\n(Erinnerungen sind hier deaktiviert, daher wurde nichts geplant.)",
    "es": "\n\n(Los recordatorios están desactivados aquí, así que no se programó nada.)",
    "ro": "\n\n(Mementourile sunt dezactivate aici, așa că nu a fost programat nimic.)",
}


def unmade_schedule_note(
    runs: Sequence[ToolRun],
    query: str,
    language: str,
    *,
    reminders_off: bool,
    claimed: bool,
    handed: bool,
) -> str | None:
    """The note on a schedule no call of the turn made, or None when none is due.

    ``handed`` is true in the deep phase, whose turn the cortex's reply already closed.
    """
    # With no store there is no list to ask for, so this note replaces the claim note.
    if reminders_off and (claimed or (asks_reminder(query) and not handed)):
        return in_language(REMINDERS_OFF_NOTE, REMINDERS_OFF_NOTES, language)
    return unscheduled_claim_note(runs, language) if claimed else None
