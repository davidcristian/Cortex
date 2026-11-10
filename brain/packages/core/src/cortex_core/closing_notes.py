"""The notes a turn that ended without an error closes with."""

from collections.abc import Iterator, Sequence

from cortex_core.access_claim import UNSEARCHED_FILES_NOTE, unsearched_files_claim
from cortex_core.chat_only_claim import KEPT_BEYOND_CHAT_NOTE, claims_chat_only
from cortex_core.conversation import ToolRun
from cortex_core.events import TurnEvent
from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, unread_folders_claim
from cortex_core.forget_claim import UNFORGOTTEN_CLAIM_NOTE, names_removal, unforgotten_claim
from cortex_core.forget_count_note import forgot_count_note, forgot_note_due
from cortex_core.forget_inside import inside_note
from cortex_core.forget_unfound_claim import (
    DECLINED_FORGET_NOTE,
    DECLINED_FORGET_NOTES,
    DELETED_UNFOUND_NOTE,
    UNMATCHED_FORGET_NOTE,
    declined_note_due,
    unfound_claim,
    unmatched_note_due,
)
from cortex_core.forget_unnamed import kept_note
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
    UNSCHEDULED_CLAIM_NOTE,
    claims_yearly,
    names_time_of_day,
    stored_time_note,
    unscheduled_claim,
)
from cortex_core.schedule_daily import DAILY_STORED_NOTE, DAILY_STORED_NOTES, names_repeat
from cortex_core.schedule_first_fire import early_first_fire_notes
from cortex_core.schedule_made_repeating import MADE_REPEATING_NOTE, MADE_REPEATING_NOTES
from cortex_core.schedule_weekday import weekday_off_dates, weekday_off_note
from cortex_core.schedule_weekly import ONCE_STORED_NOTE
from cortex_core.schedule_weekly_stored import weekly_stored_notes
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
    unkept = withheld and unkept_note_due(
        query, reply, taint.forget_spared, forget_called=taint.forget_calls > 0
    )
    shared = caps.memory is not None and caps.memory.recalls_across_chats
    stored = shared and not withheld and claims_chat_only(reply)
    # A refused call deleted nothing, and no reader names every way to claim it did. A reply saying
    # it kept the fact and naming no removal is the common end of a plain request to remember.
    unforgotten = unforgotten_claim(made, reply, unmatched=taint.forget_unmatched) or (
        taint.forget_refused and (not claims_kept(reply) or names_removal(reply))
    )
    unfound = unfound_claim(made, reply, unmatched=taint.forget_unmatched)
    missed = unmatched_note_due(
        made, unmatched=taint.forget_unmatched, deleted=taint.forget_deleted
    )
    counted = forgot_note_due(taint.forget_deleted, reply) and not unfound
    held = numbers_left_claim(reply, left=taint.forget_numbers_left, counted=counted)
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
        yield from append_note(parts, stored_time_note(taint.stored_time, language))
    if taint.daily_stored and not names_repeat(reply):
        yield from append_note(parts, in_language(DAILY_STORED_NOTE, DAILY_STORED_NOTES, language))
    if taint.made_repeating and not names_repeat(reply):
        yield from append_note(
            parts, in_language(MADE_REPEATING_NOTE, MADE_REPEATING_NOTES, language)
        )
    if taint.once_after_weekly:
        yield from append_note(parts, ONCE_STORED_NOTE)
    for note in (
        *(weekday_off_note(day, language) for day in weekday_off_dates(taint.weekday_off)),
        *early_first_fire_notes(taint.early_first_fire),
        *weekly_stored_notes(taint.weekly_stored, reply),
    ):
        yield from append_note(parts, note)
    for due, note in (
        (unkept, UNKEPT_CLAIM_NOTE),
        (stored, KEPT_BEYOND_CHAT_NOTE),
        (unforgotten, UNFORGOTTEN_CLAIM_NOTE),
        (counted, forgot_count_note(taint.forget_deleted, language)),
        (held, in_language(NUMBERS_LEFT_NOTE, NUMBERS_LEFT_NOTES, language)),
        (bool(taint.forget_kept), kept_note(taint.forget_kept, language)),
        (bool(taint.forget_inside), inside_note(taint.forget_inside)),
        (unfound, DELETED_UNFOUND_NOTE),
        (missed, UNMATCHED_FORGET_NOTE),
        (
            declined_note_due(reply, declined=taint.forget_declined),
            in_language(DECLINED_FORGET_NOTE, DECLINED_FORGET_NOTES, language),
        ),
        (unread, UNREAD_FOLDERS_NOTE),
        (unsearched, UNSEARCHED_FILES_NOTE),
    ):
        if due:
            yield from append_note(parts, note)
