"""Close a reply on a turn that refused a forget call naming a value a stored row still holds."""

from cortex_core.errors import MemoryStoreError
from cortex_core.forget_every_kept import hold_every_kept
from cortex_core.memory_old_value import hold_old_value
from cortex_core.memory_values import short_groups, whole_values
from cortex_core.turn_context import TurnCapabilities
from cortex_core.untrusted import TaintLedger

REFUSED_HELD_NOTE = (
    "\n\n(A forget call in this turn was not run, and a remembered exchange still holds the value "
    "it named. If you want that value gone, ask to forget it in a message of its own.)"
)
REFUSED_HELD_NOTES = {
    "fr": "\n\n(Un appel d'oubli n'a pas été exécuté ici, et un échange mémorisé contient "
    "toujours la valeur qu'il nommait. Si vous voulez retirer cette valeur, demandez de l'oublier "
    "dans un message à part.)",
    "de": "\n\n(Hier wurde ein Aufruf zum Vergessen nicht ausgeführt, und eine gespeicherte "
    "Unterhaltung enthält noch den Wert, den er nannte. Wenn Sie diesen Wert entfernen möchten, "
    "bitten Sie in einer eigenen Nachricht darum, ihn zu vergessen.)",
    "es": "\n\n(Aquí no se ejecutó una llamada de olvido, y un intercambio guardado todavía "
    "contiene el valor que nombraba. Si quieres quitar ese valor, pide que se olvide en un "
    "mensaje aparte.)",
    "ro": "\n\n(Un apel de uitare nu a fost executat aici, iar un schimb memorat conține încă "
    "valoarea pe care o numea. Dacă vrei ca valoarea să fie ștearsă, cere să fie uitată într-un "
    "mesaj separat.)",
}

_LIMIT = 8


def _holds(text: str, key: str) -> bool:
    """Whether ``text`` holds the whole value ``key`` as the forget tool reads one, not a date."""
    form = whole_values(text).get(key)
    return form is not None and not short_groups(form, text)


async def hold_refused_value(
    caps: TurnCapabilities, taint: TaintLedger, *, session_id: str
) -> None:
    """Set ``taint.forget_refused_held`` when a stored row holds a value a refused call named."""
    if caps.memory is None:
        return
    try:
        for text in taint.forget_refused_texts:
            for key, form in whole_values(text).items():
                rows = await caps.memory.find_value(form, session_id=session_id, limit=_LIMIT)
                if any(_holds(row.text, key) for row in rows):
                    taint.forget_refused_held = True
                    return
    except MemoryStoreError:
        # The note states what a row holds, so a store that cannot be read gives no note.
        return


async def hold_stored_values(
    caps: TurnCapabilities, taint: TaintLedger, *, query: str, reply: str, session_id: str
) -> None:
    """Record the values stored rows still hold that the closing notes name or point to."""
    await hold_old_value(caps, taint, query=query, reply=reply, session_id=session_id)
    await hold_refused_value(caps, taint, session_id=session_id)
    await hold_every_kept(caps, taint, query=query, session_id=session_id)
