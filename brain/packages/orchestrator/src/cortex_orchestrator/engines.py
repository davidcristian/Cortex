"""One Converse stream's engine, assembled from the parts the composition root built.

Its own module for the reason ``stores.py`` is: ``wiring.py`` is the one file in the brain that
legitimately grows with every capability, and it had reached the 300-line cap carrying three
nested closures over fourteen local names. Those closures were never a composition step. They
are a **per-stream factory**, run once per Converse stream rather than once per process, so they
are an object taking those names once and the root is back to reading as the list of steps it is.

Nothing here reads the environment, opens a resource, or picks an adapter: every part arrives
already built, and the two dataclasses below are frozen records of what the root decided. What
varies per stream is the ``Confirmer`` a gated tool call prompts through (ADR-0022) and the
``ProgressSink`` a delegated run surfaces onto (ADR-0010); what varies per **turn** is the
escalation slot (ADR-0030). Everything else is the shared adapters, and building an engine per
stream and an inner engine per turn costs nothing because an engine is a stateless function over
the session store (AGENTS.md's one hard rule), never a thing that remembers a conversation.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from cortex_core import (
    BrainPhase,
    BuiltinTool,
    CadenceTerms,
    Clock,
    Confirmer,
    DispatchPolicy,
    EscalatingTurnEngine,
    GenerationBounds,
    InferenceBackend,
    MemoryRecaller,
    ProgressSink,
    SessionStore,
    SubagentScheduler,
    SwapConductor,
    ToolRegistry,
    TurnCapabilities,
    TurnEngine,
    TurnRunner,
    VisionProbe,
)
from cortex_orchestrator.builders import build_cortex_tools, build_output_guardrail
from cortex_orchestrator.config import BrainRuntimeConfig
from cortex_orchestrator.swap_builders import SwapRuntime
from cortex_orchestrator.window_builders import build_history_window

__all__ = ["DeepTier", "StreamEngines"]


@dataclass(frozen=True, slots=True)
class DeepTier:
    """What a stream's engine needs to hand its turn to the deep model (ADR-0030).

    Present exactly when ``CORTEX_ESCALATION`` is on, which is what makes ``StreamEngines``
    answer a plain ``TurnEngine`` or an escalating one: three parts that are meaningless apart,
    so one of them being present while another is absent cannot be expressed.

    ``builtins`` is the deep tier's own set, and the only thing separating it from the cortex's
    is vision (ADR-0029 decision 6): no brain-tier candidate on the mount carries a projector, so
    that tier is text-only by construction. ``scheduler`` is the subagent pool's own admission
    budget, which the conductor must quiesce before a swap evicts anything (ADR-0030 decision 4),
    and it is ``None`` when delegation is off, where there is no pool to drain.
    """

    swap: SwapRuntime
    builtins: Sequence[BuiltinTool]
    scheduler: SubagentScheduler | None


@dataclass(frozen=True, slots=True)
class StreamEngines:
    """The standing parts every Converse stream's engine is built from.

    Constructed once by the composition root and handed to ``serve`` as its ``EngineFactory``
    via `for_stream`. The fields are the shared adapters and the config values the root read for
    them, so this object holds no conversation state and none of it changes between streams.

    ``sight`` is the running model server's own answer to whether it can read a picture
    (ADR-0029 live-probe addendum), re-asked on every advertisement and every call rather than
    frozen into a set; ``record_tainted_memory`` is the root's mapping of
    ``CORTEX_MEMORY_ON_TAINTED`` onto the bool the core takes (ADR-0019); ``bounds`` is how far
    each of a turn's completions may decode (ADR-0005 capped-reply addendum), applying to the
    deep phase that continues the turn as much as to the cortex's own.
    """

    sessions: SessionStore
    backend: InferenceBackend
    clock: Clock
    runtime: BrainRuntimeConfig
    memory: MemoryRecaller | None
    tools: ToolRegistry | None
    builtins: Sequence[BuiltinTool]
    policy: DispatchPolicy
    sight: VisionProbe | None
    record_tainted_memory: bool
    bounds: GenerationBounds | None
    deep: DeepTier | None

    def for_stream(self, confirmer: Confirmer, progress: ProgressSink) -> TurnRunner:
        """Build the engine one Converse stream's turns run through.

        A deployment without the handoff wired gets the plain engine, so nothing below the
        edge changes shape for it. With it wired, the escalating wrapper (ADR-0030 decision 5)
        builds a fresh slot and inner engine per turn over a conductor bound to **this**
        stream's dispatcher, so the deep model's phase runs the same audited tools the cortex
        phase did, minus the screen (ADR-0029). The deep phase carries no slot either: it
        cannot escalate to itself.
        """
        caps = self._capabilities(confirmer, progress)
        deep = self.deep
        if deep is None:
            return self._turn_engine(caps)
        phase = replace(
            caps,
            escalation=None,
            tools=build_cortex_tools(
                self.tools,
                deep.builtins,
                self.clock,
                confirmer=confirmer,
                policy=self.policy,
            ),
        )
        conductor = SwapConductor(
            deep.swap.handoffs,
            deep.swap.manager,
            BrainPhase(
                self.sessions,
                self.backend,
                self.clock,
                deep.swap.plan.brain_model,
                phase,
                CadenceTerms(deep.swap.plan.brain_decode_tps, deep.swap.manager.handoff_pace),
            ),
            deep.swap.plan,
            self.clock,
            deep.scheduler,
        )
        return EscalatingTurnEngine(
            lambda slot: self._turn_engine(replace(caps, escalation=slot)), conductor
        )

    def _capabilities(self, confirmer: Confirmer, progress: ProgressSink) -> TurnCapabilities:
        """One capability bundle per Converse stream (ADR-0022/0010).

        The stream's confirmer reaches the dispatcher and its progress sink reaches the turn, so
        a spawned subagent surfaces onto this stream's overlay; everything else is the same
        shared adapters. The window and the guardrail are built per stream too, which is where
        they were built before this module existed.
        """
        return TurnCapabilities(
            memory=self.memory,
            tools=build_cortex_tools(
                self.tools,
                self.builtins,
                self.clock,
                confirmer=confirmer,
                policy=self.policy,
                vision=self.sight,
            ),
            window=build_history_window(
                self.runtime, sessions=self.sessions, backend=self.backend, clock=self.clock
            ),
            guardrail=build_output_guardrail(self.runtime.output_guardrail),
            record_tainted_memory=self.record_tainted_memory,
            generate_titles=self.runtime.generate_titles,
            progress=progress,
            bounds=self.bounds,
        )

    def _turn_engine(self, caps: TurnCapabilities) -> TurnEngine:
        """The plain engine over the shared ports, per stream and, under a handoff, per turn."""
        return TurnEngine(
            self.sessions,
            self.backend,
            self.clock,
            cortex_model=self.runtime.cortex_model,
            capabilities=caps,
        )
