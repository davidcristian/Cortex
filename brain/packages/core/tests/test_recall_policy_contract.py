import json
from collections.abc import Callable

import pytest
from recall_policy_contract import (
    ALL_CHECKS,
    UNPRUNED_CHECKS,
    Check,
    PolicyUnderTest,
    a_pool_factor_below_one_is_refused,
)

from cortex_core import (
    InferenceError,
    JudgeRecallPolicy,
    MmrRecallPolicy,
    RawRecallPolicy,
    RecallPolicy,
    RecencyMmrRecallPolicy,
    RerankingRecallPolicy,
    ScriptedInferenceBackend,
    TextChunk,
)

_FACTOR = 4
_HALF_LIFE_SECONDS = 30 * 86400.0
_REPLY = json.dumps({"order": [5, 4, 3, 2, 1, 0, 0, 99]})


def _reranking(pool_factor: int) -> RecallPolicy:
    return RerankingRecallPolicy(
        half_life_seconds=_HALF_LIFE_SECONDS,
        recency_weight=0.5,
        dedup_threshold=0.98,
        pool_factor=pool_factor,
    )


def _mmr(pool_factor: int) -> RecallPolicy:
    return MmrRecallPolicy(relevance_weight=0.5, pool_factor=pool_factor)


def _recency_mmr(pool_factor: int) -> RecallPolicy:
    return RecencyMmrRecallPolicy(
        half_life_seconds=_HALF_LIFE_SECONDS,
        recency_weight=0.5,
        relevance_weight=0.5,
        pool_factor=pool_factor,
    )


def _judge(pool_factor: int) -> RecallPolicy:
    backend = ScriptedInferenceBackend([[TextChunk(_REPLY)]])
    return JudgeRecallPolicy(backend, "cortex", pool_factor=pool_factor)


def _unreachable_judge() -> RecallPolicy:
    backend = ScriptedInferenceBackend()
    backend.fail_with(InferenceError("llama-server is down"))
    return JudgeRecallPolicy(backend, "cortex", pool_factor=_FACTOR)


_FACTORED: dict[str, Callable[[int], RecallPolicy]] = {
    "reranking": _reranking,
    "mmr": _mmr,
    "recency-mmr": _recency_mmr,
    "judge": _judge,
}
_UNPRUNED: dict[str, Callable[[], PolicyUnderTest]] = {
    "raw": lambda: PolicyUnderTest(RawRecallPolicy(), 1),
    "mmr": lambda: PolicyUnderTest(_mmr(_FACTOR), _FACTOR),
    "recency-mmr": lambda: PolicyUnderTest(_recency_mmr(_FACTOR), _FACTOR),
}
_ALL: dict[str, Callable[[], PolicyUnderTest]] = {
    **_UNPRUNED,
    "reranking": lambda: PolicyUnderTest(_reranking(_FACTOR), _FACTOR),
    "judge": lambda: PolicyUnderTest(_judge(_FACTOR), _FACTOR),
    "unreachable-judge": lambda: PolicyUnderTest(_unreachable_judge(), _FACTOR),
}


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("name", sorted(_ALL))
async def test_the_contract_holds(check: Check, name: str) -> None:
    await check(_ALL[name]())


@pytest.mark.parametrize("check", UNPRUNED_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("name", sorted(_UNPRUNED))
async def test_an_unpruned_policy_keeps_the_pool(check: Check, name: str) -> None:
    await check(_UNPRUNED[name]())


@pytest.mark.parametrize("name", sorted(_FACTORED))
def test_a_pool_factor_below_one_is_refused(name: str) -> None:
    a_pool_factor_below_one_is_refused(_FACTORED[name])
