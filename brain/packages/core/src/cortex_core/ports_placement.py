"""The subagent placement port: where one spawn runs, against which residency (ADR-0012).

Split out of ``ports.py`` for the line cap and re-exported there, so every existing
``from cortex_core.ports import SubagentPlacer`` keeps resolving. It sits alone because it grew a
second concern the other ports do not share: the fit-test is arithmetic about **one card at one
moment**, so the placer has to be told when the model holding that card changes (ADR-0030's
handoff window), which is a verb and not an argument to ``place``.
"""

from typing import Protocol

from cortex_core.placement import Placement, PlacementRequest


class SubagentPlacer(Protocol):
    """Fit-tests a subagent onto the GPU under the VRAM soft cap, else CPU (ADR-0012).

    ``place(request)`` decides where one subagent runs: it reserves ``request.vram_gb`` and returns
    a GPU ``Placement`` when it fits the live headroom (``soft_cap - resident - placed``), else a
    CPU ``Placement`` reserving nothing (the whole model on one target, never a straddle).
    ``release(placement)`` returns the reserved VRAM to the ledger. Both are sync (a fit-test, not
    a wait) and must pair exactly once, which ``SubagentRunner`` does in a ``finally``. It
    is the GPU/VRAM contract, kept separate from the ``ModelManager``'s exclusive lease and the
    ``SubagentScheduler``'s CPU/RAM budget; the three compose at the runner (ADR-0010 decision 6).

    ``charge_handoff(resident_gb=...)`` and ``charge_standing()`` are the two edges of a brain
    handoff (ADR-0030), written by the residency scope because it is the only thing that knows
    which model holds the card. Between them the resident term names the deep model the handoff
    swapped in rather than the cortex it evicted, so the headroom describes the residency that
    exists; outside them it names the cortex again. Both are sync, idempotent, and never move the
    ``placed`` ledger: a spawn placed before an edge keeps its reservation across it and releases
    the same amount after, because its VRAM did not go anywhere when the resident changed. An
    implementation that has no notion of a resident may implement both as no-ops, which is the
    honest degenerate form and not a violation.

    ``close_gpu()`` and ``open_gpu()`` are the other pair, and they answer a different question:
    not how much of the card is free, but whether the server a GPU placement lands on is running
    at all (``residency_tiers.py``). While closed, ``place`` **must** answer CPU for every
    request, whatever the headroom says, because a fit test cannot be right about a
    ``llama-server`` that is not listening; the ledger is untouched by either verb, so a spawn
    placed before a close still releases the same amount after it. Both are sync and idempotent,
    and closing twice takes one open to reverse, since the caller counts tiers and this counts
    nothing. An implementation with no GPU target of its own may implement both as no-ops, the
    same honest degenerate form the charge pair allows. The two pairs are deliberately
    independent: a handoff charge describes a card that changed hands and heals itself when it
    changes back, while a close describes a tier that failed and is cleared only by something
    observing it serve again.
    """

    def place(self, request: PlacementRequest) -> Placement: ...

    def release(self, placement: Placement) -> None: ...

    def charge_handoff(self, *, resident_gb: float) -> None: ...

    def charge_standing(self) -> None: ...

    def close_gpu(self) -> None: ...

    def open_gpu(self) -> None: ...
