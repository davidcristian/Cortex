"""Close a reply that names no removal on a turn whose forget calls deleted rows."""

from cortex_core.note_language import in_language
from cortex_core.numbers_left_claim import says_forgotten

FORGOT_COUNT_NOTE = "\n\n(Remembered exchanges forgotten for this message: {count}.)"
FORGOT_COUNT_NOTES = {
    "fr": "\n\n(Échanges mémorisés oubliés pour ce message : {count}.)",
    "de": "\n\n(Für diese Nachricht vergessene gespeicherte Unterhaltungen: {count}.)",
    "es": "\n\n(Intercambios guardados olvidados por este mensaje: {count}.)",
    "ro": "\n\n(Schimburi memorate uitate pentru acest mesaj: {count}.)",
}


def forgot_note_due(deleted: int, reply: str) -> bool:
    """Whether a turn deleted ``deleted`` rows and its reply names no removal in any language."""
    return deleted > 0 and not says_forgotten(reply)


def forgot_count_note(deleted: int, language: str) -> str:
    """The note naming how many rows the turn deleted, in the note language ``language``."""
    return in_language(FORGOT_COUNT_NOTE, FORGOT_COUNT_NOTES, language).format(count=deleted)
