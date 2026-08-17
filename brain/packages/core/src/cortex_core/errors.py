"""Typed errors of the core: adapters wrap backend failures into these (cause chained).

Core code raises and propagates only typed errors. There is never a bare Exception, and no
adapter-specific exception ever crosses a port boundary.
"""

from enum import Enum


class SessionStoreError(Exception):
    """A SessionStore operation failed (store adapters wrap their backend's errors)."""


class InferenceError(Exception):
    """An InferenceBackend failed to produce or continue a completion."""


class MalformedToolCallError(InferenceError):
    """The server answered and the tool call the model wrote could not be assembled.

    The port's one narrower inference failure, and the distinction is between **a backend that
    did not answer** and **a model whose own output will not parse** (ADR-0005 tool-call-cut
    addendum). Every other ``InferenceError`` says the endpoint could not be reached, stalled,
    refused the request, or broke the streaming protocol, and every one of those is worth trying
    on another target: a second server may well answer. This one says the stream arrived and the
    ``arguments`` string it carried is not JSON, which the same model on another target produces
    again, because the tokens are the model's and not the transport's.

    It is what makes a cut tool call legible. A completion stopped at a token limit mid
    ``arguments`` leaves exactly this fragment, and a caller holding a ``StopLedger`` can pair the
    two facts (this error, and a completion that stopped at a limit) into the truthful verdict,
    where the wider type alone reads as a dead backend and buys a second model load to be cut at
    the same limit again. Neither fact carries the verdict alone: an unparsable fragment with no
    cap reported is a model that broke its own grammar, and a cap with an ordinary transport
    failure after it is still a transport failure.

    It is a subclass rather than a sibling so every existing ``except InferenceError`` keeps
    catching it, the ``MemoryDataError`` and ``ModelNotHostedError`` precedent: a caller with no
    use for the distinction goes on failing exactly as it did, and only the callers that can act
    on it name the narrower type.
    """


class MemoryStoreError(Exception):
    """A MemoryStore operation failed (memory adapters wrap their backend's errors)."""


class MemoryDataError(MemoryStoreError):
    """The store answered and what came back is not something this repo can read.

    The port's one narrower failure, and the distinction is between a machine that could not be
    reached and stored state that disagrees with the code reading it (ADR-0008 data-defect
    addendum). Every other ``MemoryStoreError`` says Postgres was unreachable, was shutting down,
    or refused the statement, and every one of those heals on its own: the server comes back and
    the next turn recalls normally. This one says the row was fetched and could not be decoded,
    which heals when somebody changes the data or the schema and never before, so a turn that
    degraded around it would answer thinly for ever and call it an outage.

    That heal test is the whole line: infrastructure degrades because the degradation ends, and a
    data defect propagates because nothing about it ends. ``_recalled_context`` therefore names
    this type ahead of the degrading catch and re-raises it, while ``record_exchange`` does not,
    its argument never having been about which failure it was (nothing there can be saved by
    failing, the reply having already streamed).

    It is a subclass rather than a sibling so every existing ``except MemoryStoreError`` keeps
    catching it, the ``ModelNotHostedError`` precedent: only a caller that can act on the
    distinction names the narrower type.
    """


class EmbedderError(Exception):
    """An Embedder failed to produce an embedding (adapters wrap their backend's errors)."""


class ToolError(Exception):
    """A ToolRegistry could not dispatch a call (adapters wrap their backend's errors).

    The dispatcher turns this into an ``is_error`` ``ToolResult`` so the model hears about
    the failure and can recover; a tool that ran but reported its own error is a normal
    ``is_error`` result, not this exception.
    """


class ToolNotFoundError(ToolError):
    """invoke() named a tool the registry does not know."""


class TaskStoreError(Exception):
    """A TaskStore operation failed (task-store adapters wrap their backend's errors)."""


class PreferenceStoreError(Exception):
    """A PreferenceStore operation failed (preference adapters wrap their backend's errors)."""


class HandoffStoreError(Exception):
    """A HandoffStore operation failed (handoff adapters wrap their backend's errors)."""


class SubagentAdmissionError(Exception):
    """A SubagentScheduler refused a spawn rather than queuing it: no admission is coming.

    The budget's refusals, each distinct from queuing and each carrying its own guidance in the
    message: a charge larger than the whole budget, which no peer releasing anything could ever
    fit (ADR-0012 admission-wall addendum); a pool quiescing for a model handoff, which would
    deadlock the turn against its own swap if it queued (ADR-0030); and a wait that outlasted the
    deployment's bound, the one that arrives after the caller has spent it (the ADR-0012
    bounded-admission-wait addendum). A charge within the budget otherwise waits, since it
    eventually fits as peers release. Typed rather than a bare ``ValueError``
    because ``SubagentRunner`` catches exactly this and degrades it to an ``ok=False``
    ``SubagentResult``; catching ``ValueError`` there would swallow unrelated value errors.
    Construction-time validation (a non-positive budget, a non-positive ask) stays ``ValueError``
    like every other frozen value type's, since that is a bad *value*, not a refused request.
    """


class BodyFailure(Enum):
    """How far a ``BodyGateway`` call got before it failed (ADR-0023 2026-08-08 addendum).

    The port's error currency, and a designed family rather than a transcription of gRPC's code
    list: the members are ordered by the journey a call takes, from never arriving to arriving
    and breaking. Three are **absences**, where the thing needed to do the work is not there
    (``UNREACHABLE``, ``UNSUPPORTED``, ``UNREADY``, which the ``un`` prefix marks as a set), and
    three are **events**, where something happened and it went a particular way (``REFUSED``,
    ``OVERSIZE``, ``FAULTED``).

    ``REFUSED`` rather than ``DENIED`` because ``DENIED_MSG`` is already the gated-tool denial,
    and a reader should never have to ask which denial a name means.
    """

    UNREACHABLE = "unreachable"
    """No answer arrived at all, whether for want of a route or of time. The only kind that may
    tell the caller the body could not be reached."""

    REFUSED = "refused"
    """The body answered and declined: a standing policy answer (screen capture switched off, a
    rejected seam token), not a transient one, so retrying it changes nothing."""

    UNSUPPORTED = "unsupported"
    """The body answered and has no such capability: an RPC it does not implement, or a body
    older than the brain calling it."""

    UNREADY = "unready"
    """The body answered and the host state the call needs is not there (no display, no audio
    endpoint, no notification service). It works again once the user fixes the state."""

    OVERSIZE = "oversize"
    """The work was done and its result will not fit the seam's budget. Distinct from a fault
    because nothing is broken: the same call will keep answering the same way."""

    FAULTED = "faulted"
    """Anything else: an OS fault, an answer the brain will not vouch for, a bound this
    deployment cannot ask for. The default, deliberately, so a failure nobody classified says
    the honest uninformative thing rather than claiming the body was out of reach."""


class BodyGatewayError(Exception):
    """A BodyGateway call failed, carrying the ``BodyFailure`` kind that says how.

    The gRPC adapter wraps its transport failures (a refused dial, a non-OK status) into this,
    cause chained, classifying the status code into a ``kind``; the volume and capture tools
    catch it and return an ``is_error`` result whose wording comes from that kind, so the cortex
    hears what actually happened and can recover, never a turn-killing crash.

    ``kind`` defaults to ``BodyFailure.FAULTED``: an unclassified failure must never claim the
    body was unreachable, which is the falsehood the kind was added to remove.
    """

    def __init__(self, message: str, *, kind: BodyFailure = BodyFailure.FAULTED) -> None:
        super().__init__(message)
        self.kind = kind


class ScheduleStoreError(Exception):
    """A ScheduleStore operation failed (schedule adapters wrap their backend's errors).

    A store-down signal, not a poison record: per-record corruption on the claim path is
    quarantined inside the adapter (ADR-0025 decision 1), so the ticker treats this error
    as transient (log, skip the pass, retry next poll).
    """


class ModelManagerError(Exception):
    """A ModelManager operation failed; adapters wrap their backend's errors into this."""


class ModelUnavailableError(ModelManagerError):
    """acquire() was asked for a model that is not resident, and no scope will make it so."""


class SwapFailedError(ModelManagerError):
    """A residency scope could not swap its model in, so the handoff is off (ADR-0030).

    Raised on scope ENTRY: the model failed to start, its readiness gate reported ``FAILED``, or
    the gate's bound elapsed. The scope's own ``finally`` has already restored the cortex by the
    time this surfaces, so a caller catching it is back on a serving cortex and owes the user an
    honest note, never a retry loop.
    """


class HandoffInProgressError(ModelManagerError):
    """Another handoff already owns the swap, so this one never started (ADR-0030).

    There is one GPU, so there is one handoff. Raised by the residency claim the conductor
    takes **before** it drains or evicts anything, and by a second scope entry, so the losing
    caller is refused while the machine is still untouched. Deliberately not a
    ``SwapFailedError``: the two say opposite things about what is true now. A failed swap
    leaves the cortex serving and nothing loaded; this one means the deep model IS loaded and
    is working on somebody else's turn, so the note owed to the user is the other one.
    """


class ResidencyRestoreError(ModelManagerError):
    """The cortex could not be restored after a swap, even on the retry (ADR-0030 decision 4).

    The one failure the design cannot recover from in code: the GPU holds nothing servable, so
    the scope logs loudly and raises this from its exit. ``docs/runbooks/model-swap.md`` owns
    manual recovery, and the compose ``restart`` policy plus boot recovery converge a revived
    host on the next start.
    """


class ModelHostError(Exception):
    """A ModelHost operation failed: a model process could not be started, stopped, or probed.

    The typed boundary of the process-lifecycle port (ADR-0030 decision 3). The swap turns it
    into a ``SwapFailedError`` or an aborted restore rather than letting an adapter's transport
    failure reach a turn.
    """


class ModelNotHostedError(ModelHostError):
    """The host has no such logical model at all, so no wait and no retry will produce one.

    The port's one narrower failure, and the distinction is between a **fact about the
    deployment** and a **verdict about the machine** (ADR-0030 unrostered-tier addendum). Every
    other ``ModelHostError`` says the host could not answer the question, which is a condition
    that heals: the sidecar comes back, the child stops dying, the socket answers again. This one
    says the question has no answer on this host, because the id was never in its roster, which is
    what a deployment that turned escalation on without naming ``CORTEX_MODEL_FILE_BRAIN`` gets
    for the deep tier and what a mistyped id in ``CORTEX_SWAP_EVICT_MODELS`` gets for a peer.

    It is a subclass rather than a sibling so that every existing ``except ModelHostError``
    keeps catching it: a caller that has no use for the distinction must go on failing exactly as
    it did, and only the callers that can act on it name the narrower type.
    """
