"""What the user is told while a model swap happens, or fails to (ADR-0030 decision 6)."""

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

# A deployment that turned escalation on and gave its model host no deep tier to load. Every
# handoff it is ever asked for ends here, so the note says the thing that will still be true
# tomorrow rather than inviting a retry: what is missing is a machine setting, not a moment.
UNHOSTED_TIER_NOTE = (
    "\n\n(This machine has no deep model set up, so the handoff was not started and nothing was "
    "unloaded. The answer above is what I have.)"
)
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
    """The note for each way a swap can end: what is true of the GPU right now."""
    if isinstance(error, ResidencyRestoreError):
        return RESTORE_FAILED_NOTE
    if isinstance(error, HandoffInProgressError):
        return ALREADY_ACTIVE_NOTE
    return SWAP_FAILED_NOTE
