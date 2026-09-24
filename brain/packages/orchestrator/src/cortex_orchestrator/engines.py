"""One Converse stream's engine, assembled from the parts the composition root built."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from cortex_core import (
    BrainPhase,
    BuiltinTool,
    CadenceTerms,
    Clock,
    Confirmer,
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
from cortex_orchestrator.dispatch_builders import DispatchSetup
from cortex_orchestrator.swap_builders import SwapRuntime
from cortex_orchestrator.window_builders import build_history_window

__all__ = ["DeepTier", "StreamEngines"]


@dataclass(frozen=True, slots=True)
class DeepTier:
    """What a stream's engine needs to hand its turn to the deep model."""

    swap: SwapRuntime
    builtins: Sequence[BuiltinTool]
    scheduler: SubagentScheduler | None


@dataclass(frozen=True, slots=True)
class StreamEngines:
    """The shared parts every Converse stream's engine is built from."""

    sessions: SessionStore
    backend: InferenceBackend
    clock: Clock
    runtime: BrainRuntimeConfig
    memory: MemoryRecaller | None
    tools: ToolRegistry | None
    builtins: Sequence[BuiltinTool]
    dispatch: DispatchSetup
    sight: VisionProbe | None
    record_tainted_memory: bool
    bounds: GenerationBounds | None
    deep: DeepTier | None

    def for_stream(self, confirmer: Confirmer, progress: ProgressSink) -> TurnRunner:
        """Build the engine one Converse stream's turns run through."""
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
                setup=self.dispatch,
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
            lambda slot: self._turn_engine(replace(caps, escalation=slot)),
            conductor,
            progress=progress,
        )

    def _capabilities(self, confirmer: Confirmer, progress: ProgressSink) -> TurnCapabilities:
        """One capability bundle per Converse stream."""
        return TurnCapabilities(
            memory=self.memory,
            tools=build_cortex_tools(
                self.tools,
                self.builtins,
                self.clock,
                confirmer=confirmer,
                setup=self.dispatch,
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
            residency=None if self.deep is None else self.deep.swap.manager,
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
