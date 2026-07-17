"""Boot recovery: what a restart owes a handoff the process did not survive.

The chaos suite proves the conductor converges every path it is still running; this proves the
one it cannot, because the process died. A restart fails the stranded record and converges the
GPU back onto the cortex, and it never resumes a deep phase, because replaying side-effectful
work without a request-identity design is the worse failure.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- skipping the ``transition`` to FAILED reddens
  ``test_a_stranded_record_is_failed_so_the_next_handoff_is_not_refused``;
- skipping the stop of a still-running deep model reddens
  ``test_a_deep_model_left_resident_by_a_crash_is_stopped``;
- letting a ``ModelHostError`` escape reddens ``test_an_unreachable_host_does_not_fail_the_boot``.
"""

import logging

import pytest
import swap_harness as harness
from swap_harness import RecordingHandoffStore, TickingClock

from cortex_core import (
    HandoffState,
    HandoffStoreError,
    ModelHostState,
    RecordingSleeper,
    ScriptedModelHost,
    SystemClock,
    converge_residency,
    recover_handoffs,
)


async def _recover(handoffs: RecordingHandoffStore, host: ScriptedModelHost) -> None:
    await recover_handoffs(
        handoffs, host, harness.plan(), clock=TickingClock(), sleeper=RecordingSleeper()
    )


def _stranded() -> object:
    return harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )


async def test_a_clean_boot_touches_nothing(caplog: pytest.LogCaptureFixture) -> None:
    """The usual case: no handoff was in flight and the cortex is already serving."""
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        await _recover(handoffs, host)
    assert [call for call in host.calls if call[0] != "status"] == []
    assert host.running == {"cortex"}
    assert caplog.records == []


async def test_a_stranded_record_is_failed_so_the_next_handoff_is_not_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A live record would make ``active()`` refuse every later escalation forever."""
    host = ScriptedModelHost(running=["cortex"])
    handoffs = RecordingHandoffStore()
    await handoffs.put(_stranded())  # pyright: ignore[reportArgumentType]
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_recovery"):
        await _recover(handoffs, host)
    assert await handoffs.active() is None
    failed = await handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED  # kept, not deleted: it is the diagnosis
    assert [record.message for record in caplog.records] == [
        "a handoff did not survive the restart; marking it failed"
    ]


async def test_a_deep_model_left_resident_by_a_crash_is_stopped() -> None:
    """The GPU is converged to where the conductor's finally would have left it."""
    host = ScriptedModelHost(running=["brain"])
    await _recover(RecordingHandoffStore(), host)
    assert host.running == {"cortex"}
    assert ("stop", "brain") in host.calls
    assert ("start", "cortex") in host.calls


async def test_an_evictable_tier_is_stopped_before_the_cortex_is_settled() -> None:
    """Nothing shares the GPU with the cortex on the way back up, in a fixed order."""
    host = ScriptedModelHost(running=["subagent-gpu", "brain", "cortex"])
    await converge_residency(
        host,
        harness.plan(evict_models=("subagent-gpu",)),
        clock=TickingClock(),
        sleeper=RecordingSleeper(),
    )
    stops = [call for call in host.calls if call[0] == "stop"]
    assert stops == [("stop", "subagent-gpu"), ("stop", "brain")]
    assert host.running == {"cortex"}


async def test_a_cortex_that_will_not_come_back_is_reported_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recovery cannot fix a host that will not serve, so it says so instead of pretending."""
    host = ScriptedModelHost(status_override={"cortex": ModelHostState.LOADING})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        await recover_handoffs(
            RecordingHandoffStore(),
            host,
            harness.plan(load_timeout_s=0.0),
            clock=TickingClock(),
            sleeper=RecordingSleeper(),
        )
    assert [record.message for record in caplog.records] == [
        "the cortex is not serving after boot recovery; turns will fail until it is"
    ]


async def test_an_unreachable_host_does_not_fail_the_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dead supervisor is logged and served around: the brain still starts and answers RPCs."""
    host = ScriptedModelHost(fail={("status", "brain"): "supervisor unreachable"})
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        await _recover(RecordingHandoffStore(), host)
    assert [record.message for record in caplog.records] == [
        "the model host was unreachable during boot recovery"
    ]


async def test_an_unreadable_handoff_store_does_not_fail_the_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Same posture for the store: log it, converge residency anyway, keep serving."""

    class _Unreadable(RecordingHandoffStore):
        async def active(self) -> None:
            msg = "redis is down at boot"
            raise HandoffStoreError(msg)

    host = ScriptedModelHost(running=["cortex"])
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_recovery"):
        await _recover(_Unreadable(), host)
    assert [record.message for record in caplog.records] == [
        "could not read or fail a stranded handoff at startup"
    ]
    assert host.running == {"cortex"}
