"""The notes a turn that ended without an error closes with."""

from collections.abc import Iterator, Sequence

from cortex_core.access_claim import UNSEARCHED_FILES_NOTE, unsearched_files_claim
from cortex_core.chat_only_claim import KEPT_BEYOND_CHAT_NOTE, claims_chat_only
from cortex_core.conversation import ToolRun
from cortex_core.events import TurnEvent
from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, unread_folders_claim
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, names_removal, unforgotten_claim
from cortex_core.forget_unfound_claim import DELETED_UNFOUND_NOTE, unfound_claim
from cortex_core.memory_claim import (
    UNKEPT_CLAIM_NOTE,
    claims_kept,
    memory_withheld,
    unkept_note_due,
)
from cortex_core.note_language import in_language, message_language
from cortex_core.numbers_left_claim import (
    NUMBERS_LEFT_NOTE,
    NUMBERS_LEFT_NOTES,
    numbers_left_claim,
)
from cortex_core.schedule_claim import (
    MONTHLY_STORED_NOTE,
    STORED_TIME_NOTE,
    STORED_TIME_NOTES,
    UNSCHEDULED_CLAIM_NOTE,
    claims_yearly,
    names_time_of_day,
    unscheduled_claim,
)
from cortex_core.schedule_daily import DAILY_STORED_NOTE, DAILY_STORED_NOTES, names_repeat
from cortex_core.schedule_weekly import ONCE_STORED_NOTE
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
    withheld = memory_withheld(caps, taint, made, query=query)
    unkept = withheld and unkept_note_due(query, reply)
    shared = caps.memory is not None and caps.memory.recalls_across_chats
    stored = shared and not withheld and claims_chat_only(reply)
    # A refused call deleted nothing, and no reader names every way to claim it did. A reply saying
    # it kept the fact and naming no removal is the common end of a plain request to remember.
    unforgotten = unforgotten_claim(made, reply, unmatched=taint.forget_unmatched) or (
        taint.forget_refused and (not claims_kept(reply) or names_removal(reply))
    )
    held = numbers_left_claim(reply, left=taint.forget_numbers_left)
    unfound = unfound_claim(made, reply, unmatched=taint.forget_unmatched)
    unread = unread_folders_claim(taint, query, reply)
    unsearched = unsearched_files_claim(taint, reply)
    yield from cap_note(stops, parts)
    yield from rounds_note(stops, runs, parts)
    yield from repeat_note(stops, parts)
    if claimed:
        yield from append_note(parts, UNSCHEDULED_CLAIM_NOTE)
    if taint.monthly_stored and claims_yearly(reply):
        yield from append_note(parts, MONTHLY_STORED_NOTE)
    language = message_language(query)
    if taint.stored_time and not names_time_of_day(reply):
        timed = in_language(STORED_TIME_NOTE, STORED_TIME_NOTES, language)
        yield from append_note(parts, timed.format(time=taint.stored_time))
    if taint.daily_stored and not names_repeat(reply):
        yield from append_note(parts, in_language(DAILY_STORED_NOTE, DAILY_STORED_NOTES, language))
    if taint.once_after_weekly:
        yield from append_note(parts, ONCE_STORED_NOTE)
    for due, note in (
        (unkept, UNKEPT_CLAIM_NOTE),
        (stored, KEPT_BEYOND_CHAT_NOTE),
        (unforgotten, UNFORGOTTEN_CLAIM_NOTE),
        (held, in_language(NUMBERS_LEFT_NOTE, NUMBERS_LEFT_NOTES, language)),
        (unfound, DELETED_UNFOUND_NOTE),
        (unread, UNREAD_FOLDERS_NOTE),
        (unsearched, UNSEARCHED_FILES_NOTE),
    ):
        if due:
            yield from append_note(parts, note)
