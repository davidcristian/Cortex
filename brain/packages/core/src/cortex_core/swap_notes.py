"""What the user is told while a model swap happens, or fails to (ADR-0030 decision 6).

Every string a handoff can put on the escalating turn's stream, in one place. All of it is
**app-authored**: the model never writes any of it, so none of it needs a guardrail pass, and
none of it can be steered by whatever the cortex read before it escalated (the confirm card's
per-tool reason made the same argument).

Two shapes. ``StatusUpdate(state=SWAPPING_STATE, detail=...)`` is ephemeral progress the
overlay renders as a chip: it says what the machine is doing during the minutes the swap takes
and is never persisted. A note is a ``TextDelta``: reply text, so it reads as part of the
answer. Notes are streamed but NOT persisted as a message of their own, with one deliberate
exception, ``BRAIN_FAILED_NOTE``, which is appended to the deep model's partial reply and
persisted with it, because there the note explains text the user can see in their history.

Honesty over reassurance: every failure note says what did not happen and what is true now.
``note_for`` is that rule as code: it maps each way a swap can end to the note that describes
the GPU as it stands at that moment, which is why the mapping lives beside the strings.
"""

from cortex_core.errors import (
    HandoffInProgressError,
    ModelManagerError,
    ResidencyRestoreError,
)

# The StatusUpdate.state a handoff's progress rides under. Part of the seam contract (the
# overlay renders any state's detail as a chip today, and may switch on the value later).
SWAPPING_STATE = "swapping"

DRAINING_DETAIL = "pausing delegated work before the model swap"
LOADING_DETAIL = "loading the deep model; this takes a few minutes"
WORKING_DETAIL = "the deep model is working on this"
RESTORING_DETAIL = "bringing the usual assistant back"

ALREADY_ACTIVE_NOTE = (
    "\n\n(A handoff to the deep model is already running, so this one was not started. "
    "Nothing was unloaded; ask again once the other one finishes.)"
)
STORE_FAILED_NOTE = (
    "\n\n(The handoff could not be recorded, so the deep model was not loaded and nothing was "
    "unloaded. The answer above is what I have.)"
)
# A turn that looked at the screen cannot hand over: pixels are turn-local, so the deep model
# would be given a description of a picture with no picture. The note says what the user can do.
OPAQUE_TURN_NOTE = (
    "\n\n(This turn looked at your screen, and a picture cannot be handed to the deep model, so "
    "the handoff was not started. Nothing was unloaded. Ask again in a new message if you still "
    "want the deep model.)"
)
DRAIN_TIMEOUT_NOTE = (
    "\n\n(Delegated work was still running when the handoff was due to start, so nothing was "
    "unloaded and the deep model did not take over. The answer above is what I have.)"
)
SWAP_FAILED_NOTE = (
    "\n\n(The deep model could not be loaded, so the handoff was cancelled. The usual assistant "
    "is back and the answer above is what I have.)"
)
BRAIN_FAILED_NOTE = (
    "\n\n(The deep model stopped partway through, so this answer is unfinished. The text above "
    "is everything it produced.)"
)
RESTORE_FAILED_NOTE = (
    "\n\n(The usual assistant could not be reloaded after the handoff, so the next message may "
    "fail until the machine recovers.)"
)


def note_for(error: ModelManagerError) -> str:
    """The note for each way a swap can end: what is true of the GPU right now.

    A failed restore is the graver statement (the next turn may fail too), and it wins even when
    it happened while unwinding some other failure, because it is what is true now. A refused
    claim is not a failure at all: the deep model IS loaded and the usual assistant is NOT back,
    the opposite of what the swap-failure note asserts, so it owes the other note. Only a swap
    that genuinely broke leaves the cortex serving with nothing else loaded.
    """
    if isinstance(error, ResidencyRestoreError):
        return RESTORE_FAILED_NOTE
    if isinstance(error, HandoffInProgressError):
        return ALREADY_ACTIVE_NOTE
    return SWAP_FAILED_NOTE
