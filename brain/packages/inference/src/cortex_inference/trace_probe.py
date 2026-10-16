"""Ask whether the engine behind an endpoint reads a per-request trace budget.

``GenerationBounds.trace_tokens`` is sent as llama.cpp's ``reasoning_budget_tokens``, and a build
that does not parse that key drops it without reporting anything.
"""

import logging

import httpx

from cortex_inference.request import TRACE_BUDGET_KEY

__all__ = [
    "TRACE_BUDGET_PROBE_TIMEOUT_S",
    "TraceBudgetProbe",
    "TraceProbeUnansweredError",
    "reads_a_trace_budget",
]

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

# The smallest integer outside the range a build that reads the key accepts (``-1 <= value``),
# so the probe asks the narrowest question it can. A build that parses ``reasoning_budget_tokens``
# rejects the value by name; one that does not answers the completion instead.
_OUT_OF_RANGE = -2

# Written as numbers rather than through httpx's enum, whose members are a code-and-phrase pair,
# which makes pyright read a comparison against a status code as unreachable. llama-server answers
# 503 while it loads its model, so a 5xx is a server not yet able to answer.
_REFUSED_STATUS = 400
_UNAVAILABLE_FROM = 500

# The probe's whole timeout. Sized from what the request costs on the slowest tier this repo
# ships, the subagent pick on CPU: a five-token prompt evaluates in 235 to 310 ms and one token
# decodes in 111 ms, so five seconds is roughly ten times the cost.
TRACE_BUDGET_PROBE_TIMEOUT_S = 5.0

_logger = logging.getLogger(__name__)


class TraceProbeUnansweredError(Exception):
    """No engine answered the probe: the request failed in transport or got a 5xx."""


def _probe_url(endpoint: str) -> str:
    return f"{endpoint.rstrip('/')}{_CHAT_COMPLETIONS_PATH}"


async def reads_a_trace_budget(endpoint: str, model: str, client: httpx.AsyncClient) -> bool:
    """Ask the server at ``endpoint`` whether it parses a per-request trace budget.

    A build that parses the key rejects an out-of-range value by name; any other 2xx or 4xx is a
    no, and ``TraceProbeUnansweredError`` is raised when no engine answered at all.
    """
    body: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
        TRACE_BUDGET_KEY: _OUT_OF_RANGE,
    }
    try:
        response = await client.post(
            _probe_url(endpoint), json=body, timeout=TRACE_BUDGET_PROBE_TIMEOUT_S
        )
    except httpx.HTTPError as err:
        raise TraceProbeUnansweredError(str(err)) from err
    if response.status_code >= _UNAVAILABLE_FROM:
        msg = f"the server answered {response.status_code}"
        raise TraceProbeUnansweredError(msg)
    return response.status_code == _REFUSED_STATUS and TRACE_BUDGET_KEY in response.text


class TraceBudgetProbe:
    """Whether the endpoint reads a trace budget, asked again before each request until answered.

    The answer is a fact about the engine binary, kept like a setting; it is not conversation
    state, so losing it in a restart costs one more question and nothing a store must keep.
    """

    def __init__(self, endpoint: str, model: str, client: httpx.AsyncClient) -> None:
        self._endpoint = endpoint
        self._model = model
        self._client = client
        self._answer: bool | None = None
        self._reported_unanswered = False

    async def reads(self) -> bool | None:
        """The settled answer, asking first while none has arrived; ``None`` while none has."""
        if self._answer is not None:
            return self._answer
        try:
            answer = await reads_a_trace_budget(self._endpoint, self._model, self._client)
        except TraceProbeUnansweredError as err:
            if not self._reported_unanswered:
                self._reported_unanswered = True
                _logger.warning(
                    "trace budget probe failed; asking again before the next request",
                    extra={"endpoint": _probe_url(self._endpoint), "error": str(err)},
                )
            return None
        self._answer = answer
        _logger.info(
            "trace budget probe answered",
            extra={"endpoint": _probe_url(self._endpoint), "reads_budget": answer},
        )
        return answer
