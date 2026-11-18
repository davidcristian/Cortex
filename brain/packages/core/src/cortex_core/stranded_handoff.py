"""Store that a handoff a restart interrupted got no answer, and say so on the chat's next reply."""

import logging
from collections.abc import Sequence

from cortex_core.conversation import Message, Role, ToolRun
from cortex_core.errors import SessionStoreError
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.handoff import HandoffRecord
from cortex_core.note_language import in_language, message_language
from cortex_core.ports import Clock
from cortex_core.ports_stores import SessionStore

_logger = logging.getLogger(__name__)

UNANSWERED_RUN = ToolRun(name=ESCALATE_TOOL_NAME, ok=False)

UNANSWERED_HANDOFF_NOTE = (
    "(The assistant restarted while a handoff to the deep model was running, so the request "
    "handed over got no answer. Ask it again to hand it over once more.)"
)
UNANSWERED_HANDOFF_NOTES = {
    "fr": "(L'assistant a redémarré pendant un transfert au modèle profond, donc la demande "
    "transmise n'a pas reçu de réponse. Posez-la de nouveau pour la transmettre encore une fois.)",
    "de": "(Der Assistent wurde während einer Übergabe an das tiefe Modell neu gestartet, daher "
    "hat die übergebene Anfrage keine Antwort erhalten. Stellen Sie sie erneut, um sie noch "
    "einmal zu übergeben.)",
    "es": "(El asistente se reinició durante un traspaso al modelo profundo, así que la "
    "solicitud traspasada no recibió respuesta. Pídela de nuevo para traspasarla otra vez.)",
    "ro": "(Asistentul a repornit în timpul unei predări către modelul profund, așa că cererea "
    "predată nu a primit răspuns. Pune-o din nou pentru a o preda încă o dată.)",
}
UNSURE_HANDOFF_NOTE = (
    "(The assistant restarted while a handoff to the deep model was running, and the request "
    "handed over may not have been answered. Ask it again if you see no answer to it.)"
)
_RECORD_TEXTS = frozenset(
    {UNANSWERED_HANDOFF_NOTE, UNSURE_HANDOFF_NOTE, *UNANSWERED_HANDOFF_NOTES.values()}
)


def records_no_answer(message: Message) -> bool:
    """Whether ``message`` is the record boot recovery stores for a handoff with no answer."""
    return UNANSWERED_RUN in message.runs and message.text in _RECORD_TEXTS


def unanswered_handoff_note(history: Sequence[Message]) -> str:
    """The last stored record's text as a closing note, or nothing once a later reply has it."""
    at = max((n for n, message in enumerate(history) if records_no_answer(message)), default=-1)
    if at < 0 or any(history[at].text in later.text for later in history[at + 1 :]):
        return ""
    return f"\n\n{history[at].text}"


async def record_unanswered(sessions: SessionStore, record: HandoffRecord, clock: Clock) -> None:
    """Append to the handoff's chat that it got no answer, unless the chat has a second reply.

    A chat that cannot be read gets the text saying the request may not have been answered.
    """
    fields = {"session_id": record.session_id, "turn_id": record.handoff_id}
    text = UNSURE_HANDOFF_NOTE
    try:
        history = await sessions.history(record.session_id)
    except SessionStoreError:
        _logger.exception("could not read the chat of a handoff the restart ended", extra=fields)
    else:
        turn = [message for message in history if message.turn_id == record.handoff_id]
        if sum(message.role is Role.ASSISTANT for message in turn) > 1:
            return
        asked = " ".join(message.text for message in turn if message.role is Role.USER)
        text = in_language(
            UNANSWERED_HANDOFF_NOTE, UNANSWERED_HANDOFF_NOTES, message_language(asked)
        )
    message = Message(
        role=Role.ASSISTANT,
        text=text,
        at=clock.now(),
        turn_id=record.handoff_id,
        runs=(UNANSWERED_RUN,),
    )
    try:
        await sessions.append(record.session_id, message)
    except SessionStoreError:
        _logger.exception(
            "could not store that a handoff the restart ended got no answer", extra=fields
        )
