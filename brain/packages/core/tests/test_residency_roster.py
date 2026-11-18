import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    BaselineTiers,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    converge_residency,
    record_fields,
)
from cortex_core.residency_roster import warn_of_unlisted_models

_LOGGER = "cortex_core.residency_roster"
_ROSTER = ("cortex", "brain", "subagent-gpu", "subagent-gpu-2")


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 11, 18, tzinfo=UTC)


def _plan(*evict: str, coresident: bool = False) -> ResidencyPlan:
    return ResidencyPlan(
        cortex_model="cortex", brain_model="brain", evict_models=evict, coresident=coresident
    )


async def test_a_roster_the_evict_list_covers_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(roster=_ROSTER)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert await warn_of_unlisted_models(host, _plan("subagent-gpu", "subagent-gpu-2")) == ()
    assert caplog.records == []


async def test_each_hosted_model_the_evict_list_leaves_out_is_named_in_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(roster=(*_ROSTER, "subagent-gpu-3"))
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        unlisted = await warn_of_unlisted_models(host, _plan("subagent-gpu"))
    assert unlisted == ("subagent-gpu-2", "subagent-gpu-3")
    assert [record_fields(record) for record in caplog.records] == [
        {"model": "subagent-gpu-2", "setting": "CORTEX_SWAP_EVICT_MODELS"},
        {"model": "subagent-gpu-3", "setting": "CORTEX_SWAP_EVICT_MODELS"},
    ]
    assert {record.getMessage() for record in caplog.records} == {
        "the model host has a model the evict list leaves out, so a handoff does not stop it"
    }


async def test_a_coresident_plan_stops_no_peer_so_the_host_is_not_asked() -> None:
    host = ScriptedModelHost(roster=_ROSTER)
    assert await warn_of_unlisted_models(host, _plan(coresident=True)) == ()
    assert host.calls == []


async def test_a_host_that_lists_no_models_has_nothing_to_compare(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost()
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert await warn_of_unlisted_models(host, _plan()) == ()
    assert caplog.records == []
    assert host.calls == [("roster", "")]


async def test_a_host_that_cannot_be_asked_is_one_warning_saying_the_list_is_unchecked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(roster=_ROSTER, fail={("roster", ""): "connection refused"})
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert await warn_of_unlisted_models(host, _plan()) == ()
    (record,) = caplog.records
    assert record_fields(record) == {"error": "connection refused"}
    assert "the evict list is unchecked" in record.getMessage()


async def test_boot_recovery_names_the_server_the_evict_list_leaves_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex", "subagent-gpu", "subagent-gpu-2"], roster=_ROSTER)
    plan = _plan("subagent-gpu")
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        settled = await converge_residency(
            host, plan, BaselineTiers(None), clock=_FixedClock(), sleeper=RecordingSleeper()
        )
    assert settled is True
    assert [record_fields(record)["model"] for record in caplog.records] == ["subagent-gpu-2"]
    assert host.running == {"cortex", "subagent-gpu", "subagent-gpu-2"}
