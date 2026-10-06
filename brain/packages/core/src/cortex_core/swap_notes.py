"""What the user is told while a model swap happens, or fails to."""

from cortex_core.errors import (
    HandoffInProgressError,
    ModelManagerError,
    ResidencyRestoreError,
)
from cortex_core.waits import SWAPPING

SWAPPING_STATE = SWAPPING

DRAINING_DETAIL = "pausing delegated work before the model swap"
LOADING_DETAIL = "loading the deep model; this takes a few minutes"
WORKING_DETAIL = "the deep model is working on this"
RESTORING_DETAIL = "bringing the usual assistant back"
HANDOFF_AHEAD_DETAIL = "waiting for another request's handoff to the deep model to finish"

UNHOSTED_TIER_NOTE = (
    "\n\n(This machine has no deep model set up, so the handoff was not started and nothing was "
    "unloaded. The deep model has not answered this request. No handoff can run until a deep "
    "model is set up.)"
)
ALREADY_ACTIVE_NOTE = (
    "\n\n(A handoff to the deep model is already running, so this one was not started. "
    "Nothing was unloaded; ask again once the other one finishes.)"
)
STORE_FAILED_NOTE = (
    "\n\n(The handoff could not be recorded, so the deep model was not loaded and nothing was "
    "unloaded. The deep model has not answered this request. Ask again to try the handoff once "
    "more.)"
)
OPAQUE_TURN_NOTE = (
    "\n\n(This turn holds a picture, and a picture cannot be handed to the deep model, so "
    "the handoff was not started. Nothing was unloaded. Ask again in a new message if you still "
    "want the deep model.)"
)
DRAIN_TIMEOUT_NOTE = (
    "\n\n(Delegated work was still running when the handoff was due to start, so the deep model "
    "was not loaded and nothing was unloaded. The deep model has not answered this request. Ask "
    "again once the delegated work has finished.)"
)
SWAP_FAILED_NOTE = (
    "\n\n(The deep model could not be loaded, so the handoff was cancelled and the usual "
    "assistant is back. The deep model has not answered this request. Ask again to try the "
    "handoff once more.)"
)
BRAIN_FAILED_NOTE = (
    "\n\n(The deep model stopped partway through and did not finish its answer to this request.)"
)
BRAIN_OVERFLOW_NOTE = (
    "\n\n(This conversation and what the turn has read so far are longer than the deep model's "
    "context, so it stopped before it finished its answer. A new conversation gives the deep "
    "model its whole context.)"
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
