import asyncio
import logging

import pytest
from model_host_contract import CORTEX, DEEP
from process_fakes import FakeChildProcesses, FakeProbe
from test_model_host_contract import contract_roster

from cortex_core import DeviceMemory, PlainFormatter, record_fields
from cortex_model_manager import (
    BOOT_FREE_FLOOR_MIB,
    BootFit,
    ModelSpec,
    ModelSupervisor,
    build_app,
    model_host_lifespan,
    nothing_to_close,
)

_TINY = 0.01
_FREE_AT_400000 = 24463 - 23324


class _Card:
    def __init__(self, reading: DeviceMemory | None) -> None:
        self.reading = reading
        self.reads = 0

    async def read(self) -> DeviceMemory | None:
        self.reads += 1
        return self.reading


async def _booted(probe: FakeProbe, *models: str) -> ModelSupervisor:
    supervisor = ModelSupervisor(contract_roster(), FakeChildProcesses(), probe)
    for model in models:
        await supervisor.start(model)
    return supervisor


def _serve(probe: FakeProbe, *models: str) -> None:
    for model in models:
        probe.set(contract_roster()[model].health_url, serving=True)


async def test_a_boot_set_short_of_the_floor_is_one_warning_naming_the_card_and_each_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = FakeProbe()
    supervisor = await _booted(probe, CORTEX, DEEP)
    card = _Card(DeviceMemory(free_mib=_FREE_AT_400000, total_mib=24463))
    with caplog.at_level(logging.INFO, logger="cortex_model_manager.boot_fit"):
        watch = asyncio.create_task(BootFit(poll_s=_TINY).watch(supervisor, (CORTEX, DEEP), card))
        await asyncio.sleep(_TINY * 5)
        assert card.reads == 0
        _serve(probe, CORTEX, DEEP)
        await asyncio.wait_for(watch, 1.0)
    (record,) = caplog.records
    assert PlainFormatter().format(record) == (
        "WARNING:cortex_model_manager.boot_fit:the tiers started at boot leave the card less "
        f'free memory than its floor contexts="{CORTEX}=4096 {DEEP}=4096" '
        f"floor_mib={BOOT_FREE_FLOOR_MIB} free_mib={_FREE_AT_400000} total_mib=24463"
    )
    assert card.reads == 1


async def test_a_boot_set_that_leaves_the_floor_free_is_an_info_line_and_no_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = FakeProbe()
    supervisor = await _booted(probe, CORTEX)
    _serve(probe, CORTEX)
    card = _Card(DeviceMemory(free_mib=BOOT_FREE_FLOOR_MIB, total_mib=24463))
    with caplog.at_level(logging.INFO, logger="cortex_model_manager.boot_fit"):
        await BootFit(poll_s=_TINY).watch(supervisor, (CORTEX,), card)
    (record,) = caplog.records
    assert record.levelno == logging.INFO
    assert record_fields(record)["free_mib"] == BOOT_FREE_FLOOR_MIB


async def test_a_boot_tier_never_ready_leaves_the_card_unread_with_one_info_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = FakeProbe()
    supervisor = await _booted(probe, CORTEX, DEEP)
    _serve(probe, CORTEX)
    card = _Card(DeviceMemory(free_mib=0, total_mib=24463))
    with caplog.at_level(logging.INFO, logger="cortex_model_manager.boot_fit"):
        await BootFit(poll_s=_TINY, bound_s=_TINY * 5).watch(supervisor, (CORTEX, DEEP), card)
    (record,) = caplog.records
    assert record.getMessage() == (
        "not every boot tier was ready in time, so the card was not read for fit"
    )
    assert card.reads == 0


async def test_a_host_with_no_card_reading_logs_nothing_about_fit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = FakeProbe()
    supervisor = await _booted(probe, CORTEX)
    _serve(probe, CORTEX)
    with caplog.at_level(logging.INFO, logger="cortex_model_manager.boot_fit"):
        await BootFit(poll_s=_TINY).watch(supervisor, (CORTEX, "ghost"), _Card(None))
    assert caplog.records == []


async def test_the_lifespan_runs_the_fit_watch_after_the_boot_starts_and_ends_it_at_shutdown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = FakeProbe()
    supervisor = ModelSupervisor(contract_roster(), FakeChildProcesses(), probe)
    card = _Card(DeviceMemory(free_mib=0, total_mib=24463))
    app = build_app(supervisor, boot_models=(CORTEX,), device=card, boot_fit=BootFit(poll_s=_TINY))
    with caplog.at_level(logging.WARNING, logger="cortex_model_manager.boot_fit"):
        async with app.router.lifespan_context(app):
            _serve(probe, CORTEX)
            await asyncio.sleep(_TINY * 10)
    assert [record_fields(record)["free_mib"] for record in caplog.records] == [0]


async def test_a_shutdown_before_the_boot_tiers_serve_ends_the_watch_with_the_card_unread() -> None:
    supervisor = ModelSupervisor(contract_roster(), FakeChildProcesses(), FakeProbe())
    card = _Card(DeviceMemory(free_mib=0, total_mib=24463))
    app = build_app(supervisor, boot_models=(CORTEX,), device=card, boot_fit=BootFit(poll_s=_TINY))
    async with app.router.lifespan_context(app):
        await asyncio.sleep(_TINY * 5)
    await asyncio.sleep(_TINY * 5)
    assert card.reads == 0


async def test_a_lifespan_with_no_watch_given_starts_and_stops_as_before() -> None:
    processes = FakeChildProcesses()
    supervisor = ModelSupervisor(contract_roster(), processes, FakeProbe())
    lifespan = model_host_lifespan(supervisor, (CORTEX,), nothing_to_close)
    async with lifespan(build_app(supervisor, boot_models=())):
        assert len(processes.spawned) == 1
    assert processes.spawned[0].signals == ["terminate"]


def test_a_spec_with_no_context_flag_names_its_context_unset() -> None:
    assert ModelSpec(model=CORTEX, port=8081, argv=("/app/llama-server",)).ctx_size == "unset"
    assert contract_roster()[CORTEX].ctx_size == "4096"


async def test_the_supervisors_roster_is_the_one_it_was_wired_with_and_read_only() -> None:
    supervisor = await _booted(FakeProbe())
    assert dict(supervisor.roster) == contract_roster()
    with pytest.raises(TypeError):
        supervisor.roster[CORTEX] = contract_roster()[DEEP]  # type: ignore[index]
