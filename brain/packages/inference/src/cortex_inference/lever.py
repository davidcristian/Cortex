"""Whether the engine behind an endpoint reads a per-request trace budget (ADR-0005).

``GenerationBounds.trace_tokens`` renders as llama.cpp's ``reasoning_budget_tokens``, and a build
that does not know that key ignores it in silence. Silence is the failure this repo dislikes most,
and the tier flag of the same name does better: a server started with a flag it does not know
fails at boot rather than serving as though it had been told. So the request half needs a floor,
and the floor cannot be a constant. This repo names llama.cpp by mutable tags
(``ghcr.io/ggml-org/llama.cpp:server`` and ``:server-cuda``), so which build answers is decided by
whoever last ran ``docker compose pull`` rather than by anything in this tree, and it does move:
both images on the host machine reported ``b10666-4e97ac86e`` on 2026-08-29, where the reading
this key was found on had been taken on ``b10644-d7a207411`` the day before.

**So the floor is measured rather than declared, and this is the measurement.** The engine hands
out a capability read for free, in the one place a server has to answer honestly about a key: a
build that parses ``reasoning_budget_tokens`` range-checks it and rejects a value outside the
range by name, and a build that has never heard of it ignores the whole field and answers the
completion. Measured on one model, one prompt, in one minute, against two builds:

    b10666-4e97ac86e   HTTP 400  Field 'reasoning_budget_tokens': Value must be between -1 ...
    b9870-2d973636e    HTTP 200  a completion, the field ignored

and the behaviour matches the verdict on both, measured on the one cell that separates them, a
constrained reply with the thinking switch sent: the newer build ended the thought on 58 draws of
58 with the key at zero, and the older one deliberated through the identical request on 3 of 3.

It costs one token on a build that says no and none at all on a build that says yes, since
validation runs before decoding. It is asked once, at the composition root, rather than per call:
the answer is a property of a **binary**, where the vision probe beside it answers about an
**argv** and so must be re-asked forever (ADR-0029 live-probe addendum). A model host that swaps
the cortex for the deep model starts another child of the same image, which is why one answer
covers every endpoint this backend later streams to.

Every failure is a "no". A server that cannot be reached, answers something else, or answers a
400 that does not name the key leaves the request carrying no budget, which is the request this
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

# The whole probe's leash, and it is a **boot** cost: a composition root waits this long at most
# before it decides the answer is no and goes on serving. Sized from what the request really
# costs, measured on the slowest tier this repo ships, the subagent pick on CPU: a prompt of five
# tokens evaluates in 235 to 310 ms and one token decodes in 111 ms, on a loopback network the
# vision probe beside it measured at 1.5 ms a call. Five seconds is roughly ten times that and
# short enough that a deployment pointed at nothing loses a moment of boot rather than a boot.
TRACE_LEVER_PROBE_TIMEOUT_S = 5.0

_logger = logging.getLogger(__name__)


async def reads_a_trace_budget(endpoint: str, model: str, client: httpx.AsyncClient) -> bool:
    """Ask the server at ``endpoint`` whether it parses a per-request trace budget.

    One POST carrying an out-of-range budget. A build that knows the key rejects the value and
    names the field; anything else, an answered completion above all, is read as a build that does
    not, and the verdict is logged either way because a deployment that expected the lever and did
    not get it has one line to find.

    The verdict is taken off the response **text** rather than off a parsed error object: what is
    being read is whether the engine has an opinion about this field at all, the shape it says so
    in is that engine's to change between builds, and a strict read would lose the lever on an
    upgrade instead of reporting it. A 400 from some other cause that happened to quote the field
    would read as a yes, which costs nothing: the requests this repo then sends carry values the
    engine accepts.

    The ``client`` is the caller's, as every other adapter here takes one: the probe is a single
    request with its own short leash and no business owning a connection pool past it.
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
