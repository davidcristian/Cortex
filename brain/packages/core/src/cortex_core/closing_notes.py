"""The notes a turn that ended without an error closes with."""

from collections.abc import Iterator, Sequence

from cortex_core.conversation import ToolRun
from cortex_core.events import TurnEvent
from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, unread_folders_claim
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, names_removal, unforgotten_claim
from cortex_core.memory_claim import (
    UNKEPT_CLAIM_NOTE,
    claims_kept,
    memory_withheld,
    unkept_note_due,
)
from cortex_core.schedule_claim import UNSCHEDULED_CLAIM_NOTE, unscheduled_claim
from cortex_core.stops import StopLedger
from cortex_core.turn_context import TurnCapabilities
from cortex_core.turn_output import append_note, cap_note, repeat_note, rounds_note
from cortex_core.untrusted import TaintLedger


def limit_notes(  # noqa: PLR0913 -- each claim note reads its own part of the turn
    stops: StopLedger,
    runs: Sequence[ToolRun],
    parts: list[str],
    *,
    caps: TurnCapabilities,
    taint: TaintLedger,
    query: str,
    earlier: Sequence[ToolRun] = (),
    said: Sequence[str] = (),
) -> Iterator[TurnEvent]:
    """The notes for a turn, in the order it shows them.

    ``earlier`` (the cortex's runs before a handoff) and ``said`` (the person's messages) are for
    the claims.
    """
    reply = "".join(parts)
    made = (*earlier, *runs)
    claimed = unscheduled_claim(made, reply, said)
    unkept = memory_withheld(caps, taint, made, query=query) and unkept_note_due(query, reply)
    # A refused call deleted nothing, and no reader names every way to claim it did. A reply saying
    # it kept the fact and naming no removal is the common end of a plain request to remember.
    unforgotten = unforgotten_claim(made, reply, unmatched=taint.forget_unmatched) or (
        taint.forget_refused and (not claims_kept(reply) or names_removal(reply))
    )
    unread = unread_folders_claim(taint, query, reply)
    yield from cap_note(stops, parts)
    yield from rounds_note(stops, runs, parts)
    yield from repeat_note(stops, parts)
    if claimed:
        yield from append_note(parts, UNSCHEDULED_CLAIM_NOTE)
    if unkept:
        yield from append_note(parts, UNKEPT_CLAIM_NOTE)
    if unforgotten:
        yield from append_note(parts, UNFORGOTTEN_CLAIM_NOTE)
    if unread:
        yield from append_note(parts, UNREAD_FOLDERS_NOTE)
