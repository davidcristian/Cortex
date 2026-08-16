"""Model-lifecycle ports (typing.Protocol): who owns a model process, and who owns residency.

Split from ``ports.py`` for the line cap (the ``ports_stores.py`` precedent); ``ports``
re-exports both, so ``from cortex_core.ports import ModelHost`` keeps resolving. They sit beside
``ModelManager`` by design and deliberately do not widen it: ``acquire``'s signature and its
one-lock-per-GPU semantics are unchanged by the swap (ADR-0030 decision 5, ADR-0012 decision 1),
and only one object meaningfully implements a residency scope, so it is its own protocol
(interface segregation). Method bodies are one-line ``...`` stubs; failures cross these
boundaries exclusively as the typed errors in ``errors.py``.
"""

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from cortex_core.model_host import ControlBounds, DeviceMemory, ModelHostState
from cortex_core.residency_state import ResidencyReport


class ModelHost(Protocol):
    """Starts, stops, and reports one logical model's server process (ADR-0030 decision 3).

    The process-lifecycle half ADR-0007 deferred, kept deliberately boring: ``start`` *begins*
    loading a model and ``stop`` ends it (SIGTERM then SIGKILL in the real adapter), both
    **idempotent**, so a swap may re-issue either without checking first. Readiness is observed
    only through ``status``, which is why every swap health-gates by polling it rather than
    trusting ``start`` to have finished.

    ``model`` is a logical id (ADR-0004 decision 2): artifact paths, ports, ``-ngl``, and context
    flags never cross this port, so a deployment can re-point a tier without touching the core.
    Failures surface as ``ModelHostError``, with one narrower kind beneath it: an id this host
    does not carry at all raises ``ModelNotHostedError`` from every verb, because "I have no such
    tier" is a fact about the deployment and everything else the port can fail with is a verdict
    about the machine. A caller that cannot use the difference catches the base type and behaves
    exactly as it did; the three that can are boot recovery, which must not call a tier nobody
    declared the cortex being gone, the swap in, which must not describe an id the roster never
    had as a host that broke, and the swap back, which must not fail to restore the cortex over a
    model that could never have been resident. The core's ``ScriptedModelHost`` is the scriptable
    twin CI and the chaos suite drive (delays, failures, kill-at-step, ids it does not host); the
    real supervisor adapter's live tests are ``integration``-marked, per AGENTS.md gate 3.

    ``device_memory`` is the fourth verb and the only one that is not about a process: how much of
    the card is free right now. It belongs here rather than in a port of its own because the one
    caller that reads it is the swap, which already holds all three lifecycle verbs, and because
    the answer comes off the same daemon's ``GET /health`` on the same client (a segregated port
    would be a second protocol over one adapter object for a client that uses every method of
    both). The brain's own container sees no GPU, so this is the only reading it can have.
    ``None`` is a real answer, meaning **this host cannot see a card**, and it is deliberately not
    an error: a deployment with no GPU visible to the supervisor is a normal one (CI, the scripted
    backend), while a swap that requires a fit treats an absent reading as a refusal.

    ``control_bounds`` is the fifth verb and the second that is not about a process: how long this
    host's own slowest call may legitimately take. It sits here for the same three reasons the
    card reading does (one caller, one daemon, one ``GET /health`` on one client) and answers
    ``None`` the same way, because a host that supervises no process has no stop to bound. Its
    caller is the composition root rather than the swap: the deadline the brain bounds a control
    call with is separate env from the bounds the host was given, and read at wiring time the two
    can be compared instead of merely documented. The one thing that can make that reading stale
    is the sixth verb's whole subject, a host process replaced under a brain that never restarted,
    which is why a swap reads the bounds again exactly then and never otherwise.

    ``boot_id`` is that sixth verb, and the only one that describes the answering process rather
    than the machine it supervises: a value minted per host process, so a caller can tell "the
    host my beliefs were formed against" from "a new one at the same address". It comes off the
    same ``GET /health`` on the same client as the two readings above, and ``None`` is a real
    answer once more, meaning this host will not say which boot it is: a twin that supervises no
    process and never restarts, or a daemon older than the field. It may only be compared for
    equality. It is deliberately not ordered and deliberately not a count, because a counter in a
    process that restarted starts again at the number the comparison exists to notice.
    """

    async def start(self, model: str) -> None: ...

    async def stop(self, model: str) -> None: ...

    async def status(self, model: str) -> ModelHostState: ...

    async def device_memory(self) -> DeviceMemory | None: ...

    async def control_bounds(self) -> ControlBounds | None: ...

    async def boot_id(self) -> str | None: ...


class ResidencyController(Protocol):
    """Changes which model is resident on the GPU, for the duration of a scope (ADR-0030 d5).

    ``swap_scope(model)`` is an async context manager that waits for the GPU lease to fall free
    (v1 never preempts a mid-stream round), performs the process swap through ``ModelHost``,
    serves ``model`` for the scope's duration, and **in a ``finally``** restores the cortex,
    because the swap back is the recovery path and not an optimization. Entering may raise
    ``SwapFailedError`` (nothing is left resident, and the cortex has been restored by that same
    ``finally``); a restore that fails even after its one retry raises ``ResidencyRestoreError``
    from the exit, having logged loudly, since at that point only the runbook can help.

    While a scope is active, ``ModelManager.acquire`` of any other model **waits** rather than
    raising, so a queued cortex turn on another stream blocks until restoration instead of
    failing; outside any scope, a non-resident acquire raises ``ModelUnavailableError`` exactly
    as v1 does. At most one scope is active at a time (there is one GPU): a second entry raises
    ``HandoffInProgressError`` rather than interleaving two swaps.

    ``handoff_claim()`` is the same one-GPU-one-handoff rule taken **earlier**, before anything
    is drained or evicted. Entering it either claims the whole swap sequence for its block or
    raises ``HandoffInProgressError`` at once (refuse, never queue: a queued handoff would
    hold a user's turn open for the length of somebody else's). The check and the claim happen
    with nothing awaited between them, which is what makes it a claim rather than a read: the
    conductor's own precondition would otherwise be a check-then-act race, and the loser would
    run the drain prologue and then release the drain window while the winner's deep model was
    still resident. Entering a swap scope inside a claim is the normal composition; the scope's
    own guard stays as the backstop for anything that swaps without claiming first.

    ``unhosted(model)`` is the other precondition, and the only one that is about the deployment
    rather than about this moment: whether the model host carries that logical id at all. It is
    asked **before** anything is drained or evicted, because a tier no host serves fails at the
    ``start`` in the middle of a swap, by which point the cortex is already gone and the scope's
    own ``finally`` has to load it back, which at tier scale is minutes of the assistant being
    away for a handoff that was never going to run. ``True`` says the host refused the id as one
    it does not carry (``ModelNotHostedError``); a host that could not be asked answers ``False``,
    because an unanswered question is not a refusal and a swap that goes ahead against an
    unreachable host fails at its next move with the failure that really happened. It is a
    question every time and never a remembered verdict: a roster is env one supervisor process
    read at its own boot, so an answer cached across the restart that fixes it would go on
    refusing escalation on a deployment that now works.
    """

    def swap_scope(self, model: str) -> AbstractAsyncContextManager[None]: ...

    def handoff_claim(self) -> AbstractAsyncContextManager[None]: ...

    async def unhosted(self, model: str) -> bool: ...


class ResidencyReporter(Protocol):
    """Reads what the GPU is serving right now, for the seam to answer with (ADR-0030 d6).

    Segregated from ``ResidencyController`` on purpose, and for the opposite reason: that port
    is held by the one caller allowed to *change* residency, while this one is held by a
    readiness RPC that must only ever look. The seam therefore cannot reach a swap through the
    dependency it is given, and a deployment with escalation off simply has none to give.

    ``residency()`` is **synchronous and free of I/O by contract**, which is the whole point of
    the port rather than an implementation detail: a probe arrives every few seconds precisely
    while a swap is in flight, and one that queued behind the GPU lease would hang for the whole
    load (minutes at tier scale) at exactly the moment the honest answer matters. An
    implementation therefore publishes residency as it changes and answers from that cache; it
    never asks a model host, and never waits for a lock a swap can hold.
    """

    def residency(self) -> ResidencyReport: ...
