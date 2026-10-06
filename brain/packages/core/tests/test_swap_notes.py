import pytest

from cortex_core import (
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


@pytest.mark.parametrize(
    "note", [UNHOSTED_TIER_NOTE, STORE_FAILED_NOTE, DRAIN_TIMEOUT_NOTE, SWAP_FAILED_NOTE]
)
def test_a_handoff_the_deep_model_never_ran_is_reported_unanswered(note: str) -> None:
    assert "The deep model has not answered this request." in note


@pytest.mark.parametrize(
    "note",
    [
        UNHOSTED_TIER_NOTE,
        ALREADY_ACTIVE_NOTE,
        STORE_FAILED_NOTE,
        OPAQUE_TURN_NOTE,
        DRAIN_TIMEOUT_NOTE,
        SWAP_FAILED_NOTE,
        BRAIN_FAILED_NOTE,
        BRAIN_OVERFLOW_NOTE,
        RESTORE_FAILED_NOTE,
    ],
)
def test_no_swap_note_says_what_the_text_above_it_is(note: str) -> None:
    assert "above" not in note.lower()
