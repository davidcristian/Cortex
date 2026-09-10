import asyncio
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ControlBounds,
    DeviceMemory,
    HandoffInProgressError,
    ModelHost,
    ModelHostState,
    ModelManager,
    ModelUnavailableError,
    RecordingSleeper,
    ResidencyController,
    ResidencyPlan,
    ResidencyReport,
    ResidencyReporter,
    ResidencyRestoreError,
    ScriptedModelHost,
    SwapFailedError,
    SwappingModelManager,
    record_fields,
)

_CORTEX_URL = "http://llama-cortex:8080"
_BRAIN_URL = "http://llama-brain:8081"
_ENDPOINTS = {"cortex": _CORTEX_URL, "brain": _BRAIN_URL}


class _FixedClock:
    """A clock that never advances, so a deadline is reached only if it had already passed."""

    def now(self) -> datetime:
        return datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


class _YieldingHost:
    """A host whose every operation suspends, as a real supervisor's HTTP calls do."""

    def __init__(self, inner: ScriptedModelHost) -> None:
        self._inner = inner

    async def start(self, model: str) -> None:
        await asyncio.sleep(0)
        await self._inner.start(model)

    async def stop(self, model: str) -> None:
        await asyncio.sleep(0)
        await self._inner.stop(model)

    async def status(self, model: str) -> ModelHostState:
        await asyncio.sleep(0)
        return await self._inner.status(model)

    async def device_memory(self) -> DeviceMemory | None:
        await asyncio.sleep(0)
        return await self._inner.device_memory()

    async def control_bounds(self) -> ControlBounds | None:
        await asyncio.sleep(0)
        return await self._inner.control_bounds()

    async def boot_id(self) -> str | None:
        await asyncio.sleep(0)
        return await self._inner.boot_id()


def _manager(host: ModelHost, plan: ResidencyPlan | None = None) -> SwappingModelManager:
    return SwappingModelManager(
        host, _ENDPOINTS, plan if plan is not None else _plan(), _FixedClock(), RecordingSleeper()
    )


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few times so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


async def _lease(manager: SwappingModelManager, model: str) -> str:
    async with manager.acquire(model) as lease:
        return lease.endpoint


class _HeldLease:
    """One inference round in progress, holding the GPU lease until told to finish."""

    def __init__(self, manager: SwappingModelManager, model: str) -> None:
        self._manager = manager
        self._model = model
        self.holding = asyncio.Event()
        self.release = asyncio.Event()
        self.task: asyncio.Task[None] = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async with self._manager.acquire(self._model):
            self.holding.set()
            await self.release.wait()

    async def started(self) -> None:
        async with asyncio.timeout(5.0):
            await self.holding.wait()

    async def finish(self) -> None:
        self.release.set()
        await self.task


class _OpenScope:
    """A residency scope held open until told to leave, so the test drives both boundaries."""

    def __init__(self, manager: SwappingModelManager, model: str = "brain") -> None:
        self._manager = manager
        self._model = model
        self.entered = asyncio.Event()
        self.leave = asyncio.Event()
        self.task: asyncio.Task[None] = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async with self._manager.swap_scope(self._model):
            self.entered.set()
            await self.leave.wait()

    async def start(self) -> None:
        async with asyncio.timeout(5.0):
            await self.entered.wait()

    async def finish(self) -> None:
        self.leave.set()
        await self.task


async def test_acquire_leases_the_resident_model_unchanged() -> None:
    manager: ModelManager = _manager(ScriptedModelHost(running=["cortex"]))
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL
    with pytest.raises(ModelUnavailableError, match="'brain' is not resident"):
        async with manager.acquire("brain"):
            pass  # pragma: no cover - acquire raises before the body runs
    with pytest.raises(ModelUnavailableError, match="no configured endpoint"):
        async with manager.acquire("nonesuch"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_acquire_serializes_callers_on_the_one_gpu() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    held = _HeldLease(manager, "cortex")
    await held.started()
    second = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not second.done()
    await held.finish()
    assert await second == _CORTEX_URL


async def test_the_scope_swaps_in_evicts_everything_else_and_restores_all_of_it() -> None:
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    manager = _manager(host, _plan(evict_models=("subagent-gpu",)))
    async with manager.swap_scope("brain"):
        assert host.running == {"brain"}
        async with manager.acquire("brain") as lease:
            assert lease.endpoint == _BRAIN_URL
    assert host.calls == [
        ("boot_id", ""),
        ("stop", "cortex"),
        ("stop", "subagent-gpu"),
        ("start", "brain"),
        ("status", "brain"),
        ("stop", "brain"),
        ("start", "cortex"),
        ("status", "cortex"),
        ("start", "subagent-gpu"),
    ]
    assert host.running == {"cortex", "subagent-gpu"}
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_tier_that_will_not_restart_does_not_make_the_cortex_look_gone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"], fail={("start", "subagent-gpu"): "no such device"}
    )
    manager = _manager(host, _plan(evict_models=("subagent-gpu",)))
    with caplog.at_level(logging.ERROR, logger="cortex_core.residency_moves"):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert [record.message for record in caplog.records] == [
        "a tier evicted for the handoff could not be restarted"
    ]
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_the_swap_waits_for_the_in_flight_round_to_fall_free() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    held = _HeldLease(manager, "cortex")
    await held.started()
    scope = _OpenScope(manager)
    await _settle()
    assert host.calls == []
    await held.finish()
    await scope.start()
    assert ("stop", "cortex") in host.calls
    await scope.finish()


async def test_an_acquire_of_another_model_waits_out_the_scope_instead_of_failing() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    scope = _OpenScope(manager)
    await scope.start()
    waiting = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not waiting.done()
    await scope.finish()
    async with asyncio.timeout(5.0):
        assert await waiting == _CORTEX_URL


async def test_a_queued_acquire_is_woken_even_when_the_swap_back_failed() -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(_YieldingHost(host))
    scope = _OpenScope(manager)
    await scope.start()
    waiting = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not waiting.done()
    scope.leave.set()
    with pytest.raises(ResidencyRestoreError):
        await scope.task
    async with asyncio.timeout(5.0):
        with pytest.raises(ModelUnavailableError, match="resident: None"):
            await waiting


async def test_the_restore_waits_for_the_new_resident_s_own_round() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    held = _HeldLease(manager, "brain")
    await held.started()
    scope.leave.set()
    await _settle()
    assert not scope.task.done()
    assert ("stop", "brain") not in host.calls
    await held.finish()
    await scope.task
    assert host.running == {"cortex"}


async def test_a_second_scope_is_refused_because_there_is_one_gpu() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    scope = _OpenScope(manager)
    await scope.start()
    with pytest.raises(HandoffInProgressError, match="already active"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    await scope.finish()


async def test_the_precondition_reads_the_roster_of_the_daemon_answering_right_now() -> None:
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    manager = _manager(host)
    assert await manager.unhosted("brain") is True
    host.unhosted.discard("brain")
    assert await manager.unhosted("brain") is False
    assert host.calls == [("status", "brain")] * 2
    assert host.running == {"cortex"}
    unreachable = ScriptedModelHost(running=["cortex"], fail={("status", "brain"): "refused"})
    assert await _manager(unreachable).unhosted("brain") is False


async def test_the_handoff_claim_refuses_a_second_holder_without_touching_the_host() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    async with manager.handoff_claim():
        with pytest.raises(HandoffInProgressError, match="one GPU"):
            async with manager.handoff_claim():
                pass  # pragma: no cover - entering raises before the body runs
        assert host.calls == []
        async with manager.acquire("cortex") as lease:
            assert lease.endpoint == _CORTEX_URL
    async with manager.handoff_claim():
        pass


async def test_a_claim_is_released_even_when_its_holder_is_cancelled() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    holding = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with manager.handoff_claim():
            holding.set()
            await release.wait()

    task = asyncio.create_task(hold())
    async with asyncio.timeout(5.0):
        await holding.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with manager.handoff_claim():
        pass


async def test_a_failed_swap_in_still_restores_the_cortex() -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM at load"})
    manager = _manager(host)
    with pytest.raises(SwapFailedError, match="CUDA OOM at load"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert host.running == {"cortex"}
    assert ("start", "cortex") in host.calls
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_swap_into_a_tier_the_host_never_had_says_so_rather_than_blaming_the_host() -> None:
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    manager = _manager(host)
    with pytest.raises(SwapFailedError, match="does not serve 'brain' at all"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "cortex") in host.calls
    assert host.running == {"cortex"}
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_brain_that_never_becomes_ready_fails_the_swap_at_the_gate() -> None:
    host = ScriptedModelHost(running=["cortex"], status_override={"brain": ModelHostState.LOADING})
    manager = _manager(host, _plan(load_timeout_s=0.0))
    with pytest.raises(SwapFailedError, match="did not become ready in time"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert host.running == {"cortex"}


async def test_a_brain_that_dies_at_load_fails_the_swap_with_its_state() -> None:
    host = ScriptedModelHost(running=["cortex"], status_override={"brain": ModelHostState.FAILED})
    manager = _manager(host)
    with pytest.raises(SwapFailedError, match="last state: failed"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert host.running == {"cortex"}


async def test_a_swap_is_refused_when_the_card_has_no_room_for_the_deep_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(
        running=["cortex"], device_memory=DeviceMemory(free_mib=13165, total_mib=24463)
    )
    manager = _manager(host, _plan(brain_vram_mib=19125))
    with (
        caplog.at_level(logging.ERROR, logger="cortex_core.residency_moves"),
        pytest.raises(SwapFailedError, match="needs 19125 MiB of free device memory"),
    ):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "brain") not in host.calls
    assert host.running == {"cortex"}
    (refused,) = caplog.records
    assert refused.message == (
        "the card has too little free memory for the deep model, so it was not started"
    )
    assert record_fields(refused) == {
        "model": "brain",
        "needed_mib": 19125,
        "free_mib": 13165,
        "total_mib": 24463,
    }
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_the_card_is_read_after_the_evictions_and_before_the_load() -> None:
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"],
        device_memory=DeviceMemory(free_mib=20033, total_mib=24463),
    )
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), brain_vram_mib=19125))
    async with manager.swap_scope("brain"):
        assert host.running == {"brain"}
    assert host.calls[:5] == [
        ("boot_id", ""),
        ("stop", "cortex"),
        ("stop", "subagent-gpu"),
        ("device_memory", ""),
        ("start", "brain"),
    ]


async def test_a_card_with_exactly_the_room_is_a_fit_and_one_mib_short_is_not() -> None:
    exact = ScriptedModelHost(
        running=["cortex"], device_memory=DeviceMemory(free_mib=19125, total_mib=24463)
    )
    async with _manager(exact, _plan(brain_vram_mib=19125)).swap_scope("brain"):
        assert exact.running == {"brain"}
    short = ScriptedModelHost(
        running=["cortex"], device_memory=DeviceMemory(free_mib=19124, total_mib=24463)
    )
    with pytest.raises(SwapFailedError, match="only 19124 of 24463 MiB is free"):
        async with _manager(short, _plan(brain_vram_mib=19125)).swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs


async def test_a_host_that_can_see_no_card_refuses_a_swap_that_asked_for_a_fit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host, _plan(brain_vram_mib=19125))
    with (
        caplog.at_level(logging.ERROR, logger="cortex_core.residency_moves"),
        pytest.raises(SwapFailedError, match="reports no device memory"),
    ):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "brain") not in host.calls
    assert host.running == {"cortex"}
    (refused,) = caplog.records
    assert refused.message == (
        "the model host reports no device memory, so the fit check has nothing to compare against"
    )
    assert record_fields(refused) == {"model": "brain", "needed_mib": 19125}


async def test_a_plan_with_no_measured_figure_never_asks_the_host_about_the_card() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    async with manager.swap_scope("brain"):
        assert host.running == {"brain"}
    assert ("device_memory", "") not in host.calls


async def test_a_host_that_fails_the_reading_fails_the_swap_rather_than_skipping_it() -> None:
    host = ScriptedModelHost(
        running=["cortex"], fail={("device_memory", ""): "the model host did not answer"}
    )
    manager = _manager(host, _plan(brain_vram_mib=19125))
    with pytest.raises(SwapFailedError, match="the model host did not answer"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "brain") not in host.calls
    assert host.running == {"cortex"}


async def _blow_up_inside(manager: SwappingModelManager) -> None:
    async with manager.swap_scope("brain"):
        msg = "the brain phase blew up"
        raise RuntimeError(msg)


async def test_an_exception_inside_the_scope_still_restores_the_cortex() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    with pytest.raises(RuntimeError, match="the brain phase blew up"):
        await _blow_up_inside(manager)
    assert host.running == {"cortex"}


async def test_cancelling_the_scope_still_restores_the_cortex() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    scope.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await scope.task
    assert host.running == {"cortex"}
    assert ("start", "cortex") in host.calls


async def test_a_cancelled_scope_cannot_abandon_the_restore_halfway() -> None:
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "cortex")])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    scope.leave.set()
    async with asyncio.timeout(5.0):
        await host.reached[("start", "cortex")].wait()
    scope.task.cancel()
    host.release[("start", "cortex")].set()
    with pytest.raises(asyncio.CancelledError):
        await scope.task
    assert host.running == {"cortex"}
    async with asyncio.timeout(5.0):
        assert await _lease(manager, "cortex") == _CORTEX_URL


async def test_a_restore_that_fails_once_retries_and_succeeds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail_once={("start", "cortex"): "device busy"})
    manager = _manager(host)
    with caplog.at_level(logging.WARNING):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert host.calls.count(("start", "cortex")) == 2
    assert [(record.name, record.message, record_fields(record)) for record in caplog.records] == [
        (
            "cortex_core.residency_moves",
            "the model host failed while restoring the cortex",
            {"model": "cortex"},
        ),
        (
            "cortex_core.residency_restore",
            "restoring the cortex failed; retrying",
            {"model": "cortex", "failed_model": "cortex", "attempt": 1},
        ),
    ]


async def test_a_restore_that_cannot_evict_the_deep_model_names_it_and_not_the_cortex(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail_once={("stop", "brain"): "still reaping"})
    manager = _manager(host)
    with caplog.at_level(logging.WARNING):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert host.calls.count(("stop", "brain")) == 2
    assert [(record.name, record.message, record_fields(record)) for record in caplog.records] == [
        (
            "cortex_core.residency_moves",
            "the model host failed while taking the swapped-in model off the card",
            {"model": "brain"},
        ),
        (
            "cortex_core.residency_restore",
            "restoring the cortex failed; retrying",
            {"model": "cortex", "failed_model": "brain", "attempt": 1},
        ),
    ]


async def test_a_restore_that_never_succeeds_raises_loudly_and_leaves_nothing_resident(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(host)
    with (
        caplog.at_level(logging.WARNING, logger="cortex_core.residency_restore"),
        pytest.raises(
            ResidencyRestoreError, match=r"the last of which failed on 'cortex'; manual recovery"
        ),
    ):
        async with manager.swap_scope("brain"):
            pass
    assert host.calls.count(("start", "cortex")) == 2
    assert [
        record_fields(record)
        for record in caplog.records
        if record.levelno == logging.ERROR and record.name == "cortex_core.residency_restore"
    ] == [{"model": "cortex", "failed_model": "cortex", "attempts": 2}]
    with pytest.raises(ModelUnavailableError, match="resident: None"):
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_a_restore_that_can_never_evict_gives_up_naming_the_model_that_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("stop", "brain"): "still reaping"})
    manager = _manager(host)
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(
            ResidencyRestoreError, match=r"the last of which failed on 'brain'; manual recovery"
        ),
    ):
        async with manager.swap_scope("brain"):
            pass
    assert ("start", "cortex") not in host.calls
    assert host.running == {"brain"}
    refused = (
        "cortex_core.residency_moves",
        "the model host failed while taking the swapped-in model off the card",
        {"model": "brain"},
    )
    assert [(record.name, record.message, record_fields(record)) for record in caplog.records] == [
        refused,
        refused,
        (
            "cortex_core.residency_restore",
            "could not restore the cortex after a model swap; the GPU serves nothing",
            {"model": "cortex", "failed_model": "brain", "attempts": 2},
        ),
    ]
    assert manager.residency() == RESIDENCY_LOST


async def test_a_restore_whose_gate_never_reports_ready_also_gives_up() -> None:
    host = ScriptedModelHost(running=["cortex"], status_override={"cortex": ModelHostState.LOADING})
    manager = _manager(host, _plan(load_timeout_s=0.0))
    with pytest.raises(ResidencyRestoreError, match=r"the last of which failed on 'cortex'"):
        async with manager.swap_scope("brain"):
            pass
    assert host.calls.count(("start", "cortex")) == 2


async def test_the_report_tracks_the_swap_window_from_load_to_deep_work_and_back() -> None:
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "brain")])
    manager = _manager(host)
    assert manager.residency() == RESIDENCY_SERVING
    scope = _OpenScope(manager)
    async with asyncio.timeout(5.0):
        await host.reached[("start", "brain")].wait()
    assert manager.residency() == RESIDENCY_LOADING
    host.release[("start", "brain")].set()
    await scope.start()
    assert manager.residency() == RESIDENCY_DEEP
    await scope.finish()
    assert manager.residency() == RESIDENCY_SERVING


async def test_the_report_says_the_usual_assistant_is_coming_back_while_it_restores() -> None:
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "cortex")])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    scope.leave.set()
    async with asyncio.timeout(5.0):
        await host.reached[("start", "cortex")].wait()
    assert manager.residency() == RESIDENCY_RESTORING
    host.release[("start", "cortex")].set()
    await scope.task
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_restore_that_gave_up_stops_claiming_it_is_still_restoring() -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(host)
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope("brain"):
            pass
    assert manager.residency() == RESIDENCY_LOST


async def test_the_report_answers_at_an_instant_when_the_gpu_cannot_be_leased() -> None:
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "brain")])
    manager = _manager(host)
    scope = _OpenScope(manager)
    async with asyncio.timeout(5.0):
        await host.reached[("start", "brain")].wait()
    waiting = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not waiting.done()
    assert manager.residency() == RESIDENCY_LOADING
    host.release[("start", "brain")].set()
    await scope.start()
    await scope.finish()
    async with asyncio.timeout(5.0):
        assert await waiting == _CORTEX_URL


async def test_a_claimed_handoff_still_reports_serving_because_the_cortex_still_serves() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    async with manager.handoff_claim():
        assert manager.residency() == RESIDENCY_SERVING
        async with manager.acquire("cortex") as lease:
            assert lease.endpoint == _CORTEX_URL


def test_every_published_report_says_what_the_seam_and_the_human_actually_read() -> None:
    published = [
        RESIDENCY_SERVING,
        RESIDENCY_LOADING,
        RESIDENCY_DEEP,
        RESIDENCY_RESTORING,
        RESIDENCY_LOST,
        RESIDENCY_BOOT_FAILED,
    ]
    assert published == [
        ResidencyReport(serving=True, detail=""),
        ResidencyReport(
            serving=False, detail="swapping to the deep model; this takes a few minutes"
        ),
        ResidencyReport(serving=False, detail="a deep task is in progress"),
        ResidencyReport(serving=False, detail="bringing the usual assistant back"),
        ResidencyReport(
            serving=False,
            detail="the usual assistant could not be reloaded after a deep task; recovery is "
            "manual",
        ),
        ResidencyReport(
            serving=False,
            detail="the usual assistant did not come up at startup; the model host needs attention",
        ),
    ]


async def test_boot_recovery_s_observation_replaces_the_seed_a_fresh_manager_started_with() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    await manager.publish_boot_residency(serving=False)
    assert manager.residency() == RESIDENCY_BOOT_FAILED
    await manager.publish_boot_residency(serving=True)
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_boot_that_could_not_confirm_the_cortex_still_leases_a_working_one() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    await manager.publish_boot_residency(serving=False)
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_co_resident_plan_keeps_its_peers_through_a_handoff() -> None:
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"], boot_id="daemon-a")
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), coresident=True))
    await manager.publish_boot_residency(serving=True)
    async with manager.swap_scope("brain"):
        assert host.running == {"brain", "subagent-gpu"}
    assert ("stop", "subagent-gpu") not in host.calls


async def test_a_boot_that_could_not_reach_the_host_leaves_the_first_handoff_reconciling_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"],
        boot_id="daemon-a",
        fail_once={("boot_id", ""): "connection refused"},
    )
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), coresident=True))
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        await manager.publish_boot_residency(serving=False)
        async with manager.swap_scope("brain"):
            assert host.running == {"brain", "subagent-gpu"}
    assert "could not be asked which daemon is answering" in caplog.text
    assert ("stop", "subagent-gpu") not in host.calls


async def test_a_sidecar_that_restarted_since_the_boot_publish_is_reconciled_before_the_swap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"], boot_id="daemon-a")
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), coresident=True))
    await manager.publish_boot_residency(serving=True)
    host.running = {"cortex"}
    host.boot = "daemon-b"
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        async with manager.swap_scope("brain"):
            assert host.running == {"brain", "subagent-gpu"}
    assert "the model host has been replaced since the last handoff" in caplog.text
    assert host.running == {"cortex", "subagent-gpu"}


async def test_a_restarted_sidecar_whose_bounds_outlast_the_deadline_refuses_before_evicting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    shipped = ControlBounds(probe_timeout_s=5.0, stop_grace_s=10.0, reap_timeout_s=30.0)
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a", control_bounds=shipped)
    manager = _manager(host, _plan(control_deadline_s=60.0))
    await manager.publish_boot_residency(serving=True)
    host.boot = "daemon-b"
    host.bounds = ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0)
    with (
        caplog.at_level(logging.ERROR, logger="cortex_core.residency_watch"),
        pytest.raises(SwapFailedError, match="no longer clears"),
    ):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("stop", "cortex") not in host.calls
    assert host.running == {"cortex"}
    (refused,) = caplog.records
    assert refused.message == (
        "the fresh model host's worst stop is no longer cleared by the deadline"
    )
    assert record_fields(refused) == {
        "deadline_s": 60.0,
        "worst_s": 60.0,
        "probe_timeout_s": 5.0,
        "stop_grace_s": 20.0,
        "reap_timeout_s": 35.0,
    }
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


def test_the_manager_satisfies_every_port_it_is_composed_behind() -> None:
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    leasing: ModelManager = manager
    residency: ResidencyController = manager
    reporting: ResidencyReporter = manager
    assert leasing is residency is reporting
