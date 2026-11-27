"""Close a reply to a forget of everything that keeps a stored row in words no reader reads."""

from collections.abc import Collection, Sequence

from cortex_core.conversation import ToolRun
from cortex_core.errors import MemoryStoreError
from cortex_core.escalate import hands_off
from cortex_core.forget_clauses import WHOSE, clauses
from cortex_core.forget_every import everything, store_named, unread_after_every
from cortex_core.forget_results import FORGET_CHOSEN_LIMIT
from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.memory import MemoryRecord
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.note_language import ENGLISH, forget_language, in_language
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

EVERY_KEPT_NOTE = (
    "\n\n(Nothing was deleted from memory in this turn. If you want everything else forgotten, "
    "ask in these words: {form})"
)
EVERY_KEPT_NOTES = {
    "fr": "\n\n(Rien n'a été supprimé de la mémoire ici. Si vous voulez que tout le reste soit "
    "oublié, demandez-le en ces mots : {form})",
}
# Only the languages in which the card keeps the row a form of this shape names: in German,
# Spanish and Romanian it keeps every row.
_BUT = {ENGLISH: "but", "fr": "sauf"}


def keeping_form(query: str, words: Collection[str]) -> str:
    """The forget of everything in the words of ``query`` that keeps the one word of ``words`` and
    that the card reads so; empty when there is no such form."""
    but, place = _BUT.get(forget_language(query)), everything(query)
    if but is None or place is None or len(words) != 1:
        return ""
    (word,) = words
    split, (index, at) = clauses(query), place
    run = next(
        (run for run in (split[index][at + 1 :], *split[index + 1 :]) if word in run), list[str]()
    )
    if not run:
        return ""
    spot = run.index(word)
    owner = run[spot - 1 : spot] if spot and run[spot - 1] in WHOSE else []
    form = " ".join([*split[index][: at + 1], but, *owner, word]) + "."
    form = form[:1].upper() + form[1:]
    # The form holds no content word but ``word``, and ``everything`` reads no value after it.
    return form if everything(form) is not None and asks_to_forget_keeping(form) else ""


async def hold_every_kept(
    caps: TurnCapabilities, taint: TaintLedger, *, query: str, session_id: str
) -> None:
    """Set ``taint.forget_every_kept`` to the ``keeping_form`` of the words after a forget of
    everything in ``query`` that name a stored row and that no reader reads."""
    place = everything(query)
    if caps.memory is None or place is None:
        return
    memory = caps.memory

    async def find(word: str) -> Sequence[MemoryRecord]:
        return await memory.find_text(word, session_id=session_id, limit=FORGET_CHOSEN_LIMIT + 1)

    try:
        rows, named = await store_named(query, find, ())
    except MemoryStoreError:
        # The note says the message named a stored row, so a store that cannot be read gives none.
        return
    _every, unread = unread_after_every(query, place, named)
    taint.forget_every_kept = keeping_form(query, {word for word in unread if rows.get(word)})


def every_kept_due(taint: TaintLedger, made: Sequence[ToolRun], runs: Sequence[ToolRun]) -> bool:
    """Whether a form is held and no forget of the turn ``made`` deleted a row, no card was
    declined, no old value is held, and ``runs``, this reply's calls, do not hand the turn off."""
    untrusted = any(run.ok and run.name == FORGET_UNTRUSTED_TOOL_NAME for run in made)
    held = taint.forget_deleted or taint.forget_declined or taint.old_value
    return bool(taint.forget_every_kept) and not held and not untrusted and not hands_off(runs)


def every_kept_note(form: str, language: str) -> str:
    """The note naming ``form``, in the note ``language``."""
    return in_language(EVERY_KEPT_NOTE, EVERY_KEPT_NOTES, language).format(form=form)
