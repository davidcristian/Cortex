"""Unit tests for the session-catalog RPC helpers (ADR-0021): the rename write and its clamp.

The end-to-end handler wiring is covered over a real loopback server in `test_session_reads.py`;
these pin the two pieces that live below the seam: the seam-edge title bound, and that
`rename_session` writes the *clamped* title through `SessionStore.set_title` (so the mutation
that drops the clamp, or the one that never writes, each reddens exactly one test here).
"""

from collections.abc import Sequence

from cortex_core import Message, SessionSummary
from cortex_orchestrator.session_rpc import (
    MAX_TITLE_INPUT,
    clamp_title,
    rename_session,
)
from cortex_seam import RenameSessionReply


class RecordingStore:
    """A SessionStore that records the last `set_title` it was asked to write.

    Only `set_title` is exercised here; the reads satisfy the port but are never called.
    """

    def __init__(self) -> None:
        self.set_title_calls: list[tuple[str, str]] = []

    async def append(self, session_id: str, message: Message) -> None:
        del session_id, message

    async def history(self, session_id: str) -> Sequence[Message]:
        del session_id
        return ()

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        del limit
        return ()

    async def set_title(self, session_id: str, title: str) -> None:
        self.set_title_calls.append((session_id, title))


def test_clamp_title_passes_a_short_title_through_unchanged() -> None:
    assert clamp_title("Everything about cats") == "Everything about cats"


def test_clamp_title_keeps_an_empty_title_empty() -> None:
    # "" is the clear-the-override signal and must survive the bound intact.
    assert clamp_title("") == ""


def test_clamp_title_bounds_an_overlong_title() -> None:
    bounded = clamp_title("x" * (MAX_TITLE_INPUT + 500))
    assert len(bounded) == MAX_TITLE_INPUT


async def test_rename_session_writes_the_clamped_title_via_set_title() -> None:
    store = RecordingStore()
    reply = await rename_session(store, "alpha", "y" * (MAX_TITLE_INPUT + 10))
    assert store.set_title_calls == [("alpha", "y" * MAX_TITLE_INPUT)]
    assert isinstance(reply, RenameSessionReply)


async def test_rename_session_passes_an_empty_title_to_clear_the_override() -> None:
    store = RecordingStore()
    await rename_session(store, "beta", "")
    assert store.set_title_calls == [("beta", "")]
