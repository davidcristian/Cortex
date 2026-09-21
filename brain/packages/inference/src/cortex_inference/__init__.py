"""llama.cpp adapter for the core's InferenceBackend port (docs/modules/brain-inference.md)."""

from cortex_inference.backend import LlamaCppBackend
from cortex_inference.trace_probe import TRACE_BUDGET_PROBE_TIMEOUT_S, reads_a_trace_budget

__all__ = ["TRACE_BUDGET_PROBE_TIMEOUT_S", "LlamaCppBackend", "reads_a_trace_budget"]
