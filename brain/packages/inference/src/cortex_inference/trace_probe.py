"""Ask whether the engine behind an endpoint reads a per-request trace budget.

``GenerationBounds.trace_tokens`` is sent as llama.cpp's ``reasoning_budget_tokens``, and a build
that does not parse that key drops it without reporting anything.
"""

import logging

import httpx

from cortex_inference.request import TRACE_BUDGET_KEY

__all__ = ["TRACE_LEVER_PROBE_TIMEOUT_S", "reads_a_trace_budget"]

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

# The smallest integer outside the range a build that reads the key accepts (``-1 <= value``),
# so the probe asks the narrowest question it can. A build that parses ``reasoning_budget_tokens``
# rejects the value by name; one that does not answers the completion instead.
_OUT_OF_RANGE = -2

# Written as the number rather than through httpx's enum, whose members are a code-and-phrase
# pair, which makes pyright read a comparison against a status code as unreachable.
_REFUSED_STATUS = 400

# The probe's whole timeout, paid at boot. Sized from what the request costs on the slowest tier
# this repo ships, the subagent pick on CPU: a five-token prompt evaluates in 235 to 310 ms and
# one token decodes in 111 ms, so five seconds is roughly ten times the cost.
TRACE_LEVER_PROBE_TIMEOUT_S = 5.0

_logger = logging.getLogger(__name__)


async def reads_a_trace_budget(endpoint: str, model: str, client: httpx.AsyncClient) -> bool:
    """Ask the server at ``endpoint`` whether it parses a per-request trace budget.

    One POST with an out-of-range budget: a build that parses the key rejects the value and
    names the field, and any other answer is read as a build that does not parse it.
    """
    url = f"{endpoint.rstrip('/')}{_CHAT_COMPLETIONS_PATH}"
    body: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
        TRACE_BUDGET_KEY: _OUT_OF_RANGE,
    }
    try:
        response = await client.post(url, json=body)
    except httpx.HTTPError as err:
        _logger.warning("trace lever probe failed", extra={"endpoint": url, "error": str(err)})
        return False
    reads = response.status_code == _REFUSED_STATUS and TRACE_BUDGET_KEY in response.text
    _logger.info("trace lever probe answered", extra={"endpoint": url, "lever": reads})
    return reads
