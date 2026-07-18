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

from cortex_core.model_host import ModelHostState
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
    Failures surface as ``ModelHostError``. The core's ``ScriptedModelHost`` is the scriptable
    twin CI and the chaos suite drive (delays, failures, kill-at-step); the real supervisor
    adapter's live tests are ``integration``-marked, per AGENTS.md gate 3.
    """

    async def start(self, model: str) -> None: ...

    async def stop(self, model: str) -> None: ...

    async def status(self, model: str) -> ModelHostState: ...


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
    """

    def swap_scope(self, model: str) -> AbstractAsyncContextManager[None]: ...

    def handoff_claim(self) -> AbstractAsyncContextManager[None]: ...


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
