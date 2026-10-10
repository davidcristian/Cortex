from collections.abc import Callable, Iterator

from cortex_core import (
    AsyncioSleeper,
    FencedServingProbe,
    ResidencyPlan,
    ScriptedModelHost,
    ScriptedServingProbe,
    ServingWatch,
    SwappingModelManager,
    SystemClock,
)

_DOWN = "the scripted part is down"


def _fence(answers: list[bool]) -> Callable[[], bool]:
    readings: Iterator[bool] = iter(answers)
    return lambda: next(readings)


async def test_a_reading_taken_between_handoffs_is_the_wrapped_probes_own() -> None:
    probe = ScriptedServingProbe("the cortex", answer=_DOWN)
    fenced = FencedServingProbe(probe, _fence([True, True]))
    assert fenced.part == "the cortex"
    assert await fenced.fault() == _DOWN


async def test_a_handoff_holding_the_card_before_the_ask_skips_it() -> None:
    probe = ScriptedServingProbe(answer=_DOWN)
    assert await FencedServingProbe(probe, _fence([False])).fault() is None
    assert probe.calls == 0


async def test_a_handoff_claimed_during_the_ask_drops_the_reading() -> None:
    probe = ScriptedServingProbe(answer=_DOWN)
    assert await FencedServingProbe(probe, _fence([True, False])).fault() is None
    assert probe.calls == 1


async def test_the_managers_fence_is_closed_from_the_claim_to_the_end_of_the_swap_back() -> None:
    manager = SwappingModelManager(
        ScriptedModelHost(running=["cortex"]),
        {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"},
        ResidencyPlan(cortex_model="cortex", brain_model="brain"),
        SystemClock(),
        AsyncioSleeper(),
    )
    watch = ServingWatch(
        [FencedServingProbe(ScriptedServingProbe(answer=_DOWN), manager.between_handoffs)]
    )
    async with manager.handoff_claim():
        await watch.refresh()
        assert watch.fault() is None
        async with manager.swap_scope("brain"):
            await watch.refresh()
            assert watch.fault() is None
    await watch.refresh()
    assert watch.fault() == _DOWN
