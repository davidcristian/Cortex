import asyncio
import logging

import pytest

from cortex_core import (
    SERVING_CHECK_INTERVAL_S,
    SERVING_CHECK_TIMEOUT_S,
    ScriptedServingProbe,
    ServingWatch,
)


class _BreakingProbe:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def part(self) -> str:
        return "the breaking part"

    async def fault(self) -> str | None:
        self.calls += 1
        if self.calls == 2:
            msg = "a probe that breaks its contract once"
            raise RuntimeError(msg)
        return None


def test_a_reading_is_under_one_interval_and_a_check_ends_inside_it() -> None:
    assert SERVING_CHECK_TIMEOUT_S < SERVING_CHECK_INTERVAL_S <= 5.0


async def test_a_watch_never_refreshed_reports_no_fault() -> None:
    assert ServingWatch([ScriptedServingProbe(answer="down")]).fault() is None


async def test_a_watch_with_no_probes_reports_no_fault() -> None:
    watch = ServingWatch([])
    await watch.refresh()
    assert watch.fault() is None


async def test_the_first_fault_in_probe_order_wins() -> None:
    cortex = ScriptedServingProbe("the cortex", answer="the cortex is down")
    store = ScriptedServingProbe("the store", answer="the store is down")
    watch = ServingWatch([cortex, store])
    await watch.refresh()
    assert watch.fault() == "the cortex is down"
    cortex.answer = None
    await watch.refresh()
    assert watch.fault() == "the store is down"
    store.answer = None
    await watch.refresh()
    assert watch.fault() is None


async def test_a_probe_that_does_not_answer_in_time_is_a_fault_naming_its_part() -> None:
    silent = ScriptedServingProbe("the store")
    silent.silent = True
    watch = ServingWatch([silent], timeout_s=0.01)
    await watch.refresh()
    assert watch.fault() == "the store did not answer within 0.01 s"


async def test_probes_are_asked_at_once_so_a_pass_takes_one_timeout() -> None:
    probes = [ScriptedServingProbe(f"part {n}") for n in range(3)]
    for probe in probes:
        probe.silent = True
    watch = ServingWatch(probes, timeout_s=0.2)
    loop = asyncio.get_running_loop()
    started = loop.time()
    await watch.refresh()
    assert loop.time() - started < 0.5
    assert watch.fault() == "part 0 did not answer within 0.2 s"


async def test_a_change_is_logged_once_each_way(caplog: pytest.LogCaptureFixture) -> None:
    probe = ScriptedServingProbe(answer="the store is down")
    watch = ServingWatch([probe])
    with caplog.at_level(logging.INFO, logger="cortex_core.serving_watch"):
        await watch.refresh()
        await watch.refresh()
        probe.answer = None
        await watch.refresh()
        await watch.refresh()
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, "a part a turn needs is not answering"),
        (logging.INFO, "every part a turn needs is answering again"),
    ]
    assert caplog.records[0].__dict__["fault"] == "the store is down"


async def test_start_takes_a_reading_before_it_returns_then_keeps_it_current() -> None:
    probe = ScriptedServingProbe(answer="the store is down")
    watch = ServingWatch([probe], interval_s=0.01)
    await watch.start()
    assert watch.fault() == "the store is down"
    probe.answer = None
    for _ in range(200):
        if watch.fault() is None:
            break
        await asyncio.sleep(0.01)
    assert watch.fault() is None
    await watch.aclose()
    calls = probe.calls
    await asyncio.sleep(0.05)
    assert probe.calls == calls


async def test_a_second_start_does_not_start_a_second_loop() -> None:
    probe = ScriptedServingProbe()
    watch = ServingWatch([probe], interval_s=60.0)
    await watch.start()
    await watch.start()
    assert probe.calls == 1
    await watch.aclose()


async def test_closing_a_watch_never_started_does_nothing() -> None:
    watch = ServingWatch([ScriptedServingProbe()])
    await watch.aclose()
    assert watch.fault() is None


async def test_the_loop_outlives_a_pass_that_raises(caplog: pytest.LogCaptureFixture) -> None:
    probe = _BreakingProbe()
    watch = ServingWatch([probe], interval_s=0.01)
    with caplog.at_level(logging.ERROR, logger="cortex_core.serving_watch"):
        await watch.start()
        for _ in range(200):
            if probe.calls >= 3:
                break
            await asyncio.sleep(0.01)
        await watch.aclose()
    assert probe.calls >= 3
    assert [r.getMessage() for r in caplog.records] == [
        "a serving check failed; the next pass asks again"
    ]
