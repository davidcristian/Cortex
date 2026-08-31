"""Whether the engine behind an endpoint reads a per-request trace budget (ADR-0005).

``GenerationBounds.trace_tokens`` renders as llama.cpp's ``reasoning_budget_tokens``, and a build
that does not know that key drops it without reporting anything, where the tier flag of the same
name fails a server at startup. So the request half needs a floor, and that floor cannot be a
constant: this repo names llama.cpp by mutable tags (``ghcr.io/ggml-org/llama.cpp:server`` and
``:server-cuda``), so which build answers is decided by whoever last ran ``docker compose pull``,
and it does move.

The floor is measured instead. A build that parses ``reasoning_budget_tokens`` range-checks it and
rejects an out-of-range value by name, and a build that has never read the key ignores the field
and answers the completion. ADR-0005's request-lever addendum carries the two builds this was
measured on and the one cell that separates them; docs/modules/brain-inference.md states the
contract.

The probe costs one token on a build that answers 400 and none on one that answers 200, since
validation runs before decoding. It is asked once, at the composition root, because the answer is
a property of a binary, where the vision probe beside it answers about an argv and so is re-asked
forever (ADR-0029 live-probe addendum). A model host that swaps the cortex for the deep model
starts another child of the same image, so one answer covers every endpoint this backend later
streams to.

Every failure is read as a no: a server that cannot be reached, answers something else, or answers
a 400 that does not name the key leaves the request carrying no budget, which is the request this
repo sent before any of this existed.
"""

import logging

import httpx

from cortex_inference.request import TRACE_BUDGET_KEY

__all__ = ["TRACE_LEVER_PROBE_TIMEOUT_S", "reads_a_trace_budget"]

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"

# The value the probe is built on: the smallest integer outside the range a knowing build accepts
# (``-1 <= value``), so the probe asks the narrowest question it can. A future build that widened
# the range would answer 200 and be read as not knowing the key, which is the safe direction: the
# request goes back to carrying no budget rather than carrying one nothing enforces.
_OUT_OF_RANGE = -2

# The status a build that parses the key answers that value with. Spelled as the number rather
# than through httpx's own enum, whose members are typed as a code-and-phrase pair and so cannot be
# compared to a status code without pyright calling the comparison unreachable.
_REFUSED_STATUS = 400

# The probe's whole timeout, paid at boot: a composition root waits this long at most, then reads
# the answer as no and goes on serving. Sized from what the request really costs, measured on the
# slowest tier this repo ships, the subagent pick on CPU: a prompt of five tokens evaluates in 235
# to 310 ms and one token decodes in 111 ms, on a loopback network the vision probe beside it
# measured at 1.5 ms a call. Five seconds is roughly ten times that and short enough that a
# deployment pointed at nothing loses a moment of boot rather than a boot.
TRACE_LEVER_PROBE_TIMEOUT_S = 5.0

_logger = logging.getLogger(__name__)


async def reads_a_trace_budget(endpoint: str, model: str, client: httpx.AsyncClient) -> bool:
    """Ask the server at ``endpoint`` whether it parses a per-request trace budget.

    One POST carrying an out-of-range budget. A build that parses the key rejects the value and
    names the field; anything else, an answered completion above all, is read as a build that does
    not parse it. The result is logged either way, so a deployment that expected the lever and did
    not get it has one line to find.

    The result is taken off the response text rather than off a parsed error object, because what
    is being read is whether the engine parses this field at all, and the shape of that answer
    changes between builds: a strict read would lose the lever on an upgrade. A 400 from some other
    cause that happened to quote the field reads as a yes, which costs nothing, since the requests
    this repo then sends carry values the engine accepts.

    The ``client`` is the caller's, as every other adapter here takes one: the probe is a single
    request with its own short timeout and does not own a connection pool past it.
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
