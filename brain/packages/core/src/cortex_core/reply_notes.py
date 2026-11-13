"""Leave the notes the brain appends out of a reply, so a reader sees only what the model wrote."""

import re
from collections.abc import Mapping
from string import Formatter

from cortex_core.access_claim import UNSEARCHED_FILES_NOTE, UNSEARCHED_FILES_NOTES
from cortex_core.chat_only_claim import KEPT_BEYOND_CHAT_NOTE, KEPT_BEYOND_CHAT_NOTES
from cortex_core.file_claim import UNREAD_FOLDERS_NOTE, UNREAD_FOLDERS_NOTES
from cortex_core.forget_claim import (
    HANDED_CLAIM_NOTE,
    HANDED_CLAIM_NOTES,
    UNFORGOTTEN_CLAIM_NOTE,
    UNFORGOTTEN_CLAIM_NOTES,
)
from cortex_core.forget_count_note import FORGOT_COUNT_NOTE, FORGOT_COUNT_NOTES
from cortex_core.forget_inside import INSIDE_NOTE, INSIDE_NOTES
from cortex_core.forget_longer import LONGER_NOTE, LONGER_NOTES
from cortex_core.forget_uncalled import (
    HANDED_FORGET_NOTE,
    HANDED_FORGET_NOTES,
    UNCALLED_FORGET_NOTE,
    UNCALLED_FORGET_NOTES,
)
from cortex_core.forget_unfound_claim import (
    DECLINED_FORGET_NOTE,
    DECLINED_FORGET_NOTES,
    DELETED_UNFOUND_NOTE,
    DELETED_UNFOUND_NOTES,
    HANDED_UNMATCHED_NOTE,
    HANDED_UNMATCHED_NOTES,
    UNMATCHED_FORGET_NOTE,
    UNMATCHED_FORGET_NOTES,
)
from cortex_core.forget_unnamed import KEPT_NOTE, KEPT_NOTES
from cortex_core.memory_claim import UNKEPT_CLAIM_NOTE, UNKEPT_CLAIM_NOTES
from cortex_core.memory_old_value import OLD_VALUE_NOTE, OLD_VALUE_NOTES
from cortex_core.numbers_left_claim import NUMBERS_LEFT_NOTE, NUMBERS_LEFT_NOTES
from cortex_core.repeat_watch import REPEATED_LINE_NOTE, REPEATED_LINE_NOTES
from cortex_core.rounds_languages import ROUNDS_SPENT_NOTES
from cortex_core.schedule_cancelled import CANCELLED_NOTE, CANCELLED_NOTES
from cortex_core.schedule_claim import (
    LISTED_UNCHANGED_NOTE,
    LISTED_UNCHANGED_NOTES,
    MONTHLY_STORED_NOTE,
    MONTHLY_STORED_NOTES,
    STORED_TIME_NOTE,
    STORED_TIME_NOTES,
    UNSCHEDULED_CLAIM_NOTE,
    UNSCHEDULED_CLAIM_NOTES,
)
from cortex_core.schedule_daily import DAILY_STORED_NOTE, DAILY_STORED_NOTES
from cortex_core.schedule_first_fire import FIRST_FIRE_NOTE, FIRST_FIRE_NOTES
from cortex_core.schedule_made_repeating import MADE_REPEATING_NOTE, MADE_REPEATING_NOTES
from cortex_core.schedule_quoted import QUOTED_STORED_NOTE, QUOTED_STORED_NOTES
from cortex_core.schedule_weekday import WEEKDAY_OFF_NOTE, WEEKDAY_OFF_NOTES
from cortex_core.schedule_weekly import ONCE_STORED_NOTE, ONCE_STORED_NOTES
from cortex_core.schedule_weekly_stored import WEEKLY_STORED_NOTE, WEEKLY_STORED_NOTES
from cortex_core.swap_notes import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    BRAIN_OVERFLOW_NOTE,
    DRAIN_TIMEOUT_NOTE,
    OPAQUE_TURN_NOTE,
    RESTORE_FAILED_NOTE,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    UNHOSTED_TIER_NOTE,
)
from cortex_core.turn_output import (
    CONTEXT_OVERFLOW_NO_TEXT_NOTE,
    CONTEXT_OVERFLOW_NOTE,
    MESSAGE_OVERFLOW_NOTE,
    REPLY_CAPPED_NOTE,
    REPLY_CAPPED_NOTES,
    ROUNDS_SPENT_NOTE,
    UNREADABLE_CALL_NO_TEXT_NOTE,
    UNREADABLE_CALL_NOTE,
)


def _forms(english: str, others: Mapping[str, str]) -> tuple[str, ...]:
    return (english, *others.values())


REPLY_NOTES: tuple[str, ...] = (
    *_forms(UNSEARCHED_FILES_NOTE, UNSEARCHED_FILES_NOTES),
    *_forms(KEPT_BEYOND_CHAT_NOTE, KEPT_BEYOND_CHAT_NOTES),
    *_forms(UNREAD_FOLDERS_NOTE, UNREAD_FOLDERS_NOTES),
    *_forms(HANDED_CLAIM_NOTE, HANDED_CLAIM_NOTES),
    *_forms(UNFORGOTTEN_CLAIM_NOTE, UNFORGOTTEN_CLAIM_NOTES),
    *_forms(FORGOT_COUNT_NOTE, FORGOT_COUNT_NOTES),
    *_forms(INSIDE_NOTE, INSIDE_NOTES),
    *_forms(LONGER_NOTE, LONGER_NOTES),
    *_forms(HANDED_FORGET_NOTE, HANDED_FORGET_NOTES),
    *_forms(UNCALLED_FORGET_NOTE, UNCALLED_FORGET_NOTES),
    *_forms(DECLINED_FORGET_NOTE, DECLINED_FORGET_NOTES),
    *_forms(DELETED_UNFOUND_NOTE, DELETED_UNFOUND_NOTES),
    *_forms(HANDED_UNMATCHED_NOTE, HANDED_UNMATCHED_NOTES),
    *_forms(UNMATCHED_FORGET_NOTE, UNMATCHED_FORGET_NOTES),
    *_forms(KEPT_NOTE, KEPT_NOTES),
    *_forms(UNKEPT_CLAIM_NOTE, UNKEPT_CLAIM_NOTES),
    *_forms(OLD_VALUE_NOTE, OLD_VALUE_NOTES),
    *_forms(NUMBERS_LEFT_NOTE, NUMBERS_LEFT_NOTES),
    *_forms(REPEATED_LINE_NOTE, REPEATED_LINE_NOTES),
    *_forms(ROUNDS_SPENT_NOTE, ROUNDS_SPENT_NOTES),
    *_forms(CANCELLED_NOTE, CANCELLED_NOTES),
    *_forms(LISTED_UNCHANGED_NOTE, LISTED_UNCHANGED_NOTES),
    *_forms(MONTHLY_STORED_NOTE, MONTHLY_STORED_NOTES),
    *_forms(STORED_TIME_NOTE, STORED_TIME_NOTES),
    *_forms(UNSCHEDULED_CLAIM_NOTE, UNSCHEDULED_CLAIM_NOTES),
    *_forms(DAILY_STORED_NOTE, DAILY_STORED_NOTES),
    *_forms(FIRST_FIRE_NOTE, FIRST_FIRE_NOTES),
    *_forms(MADE_REPEATING_NOTE, MADE_REPEATING_NOTES),
    *_forms(QUOTED_STORED_NOTE, QUOTED_STORED_NOTES),
    *_forms(WEEKDAY_OFF_NOTE, WEEKDAY_OFF_NOTES),
    *_forms(ONCE_STORED_NOTE, ONCE_STORED_NOTES),
    *_forms(WEEKLY_STORED_NOTE, WEEKLY_STORED_NOTES),
    *_forms(REPLY_CAPPED_NOTE, REPLY_CAPPED_NOTES),
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    BRAIN_OVERFLOW_NOTE,
    DRAIN_TIMEOUT_NOTE,
    OPAQUE_TURN_NOTE,
    RESTORE_FAILED_NOTE,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    UNHOSTED_TIER_NOTE,
    CONTEXT_OVERFLOW_NO_TEXT_NOTE,
    CONTEXT_OVERFLOW_NOTE,
    MESSAGE_OVERFLOW_NOTE,
    UNREADABLE_CALL_NO_TEXT_NOTE,
    UNREADABLE_CALL_NOTE,
)
# A note that does not close its bracket opens a list, one "- " line per item.
_ITEMS = r"(?:\n- [^\n]*)*\)"


def _pattern(note: str) -> str:
    """A search for ``note`` as the brain appends it, each format field one line of any text."""
    text = note.lstrip("\n")
    parts = [
        re.escape(literal) + (r"[^\n]+?" if field is not None else "")
        for literal, field, _spec, _conversion in Formatter().parse(text)
    ]
    return "".join(parts) + ("" if text.endswith(")") else _ITEMS)


_NOTE_AT_END = re.compile(
    r"(?:\A|\n)(?:" + "|".join(_pattern(note) for note in REPLY_NOTES) + r")\s*\Z"
)


def model_text(reply: str) -> str:
    """``reply`` less the notes the brain appended after the model's text."""
    text = reply
    while (found := _NOTE_AT_END.search(text)) is not None:
        text = text[: found.start()]
    return text
