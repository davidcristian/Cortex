"""Tool-dispatch configuration (ADR-0009): env-driven, root-read only."""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    ALWAYS_SALIENT,
    ESCALATE_GATE_REASON,
    ESCALATE_TOOL_NAME,
    MAX_IDENTICAL_DISPATCHES,
    MAX_TOOL_DISPATCHES,
    SPAWN_TOOL_NAME,
    DispatchPolicy,
    RepeatSalience,
    SaliencePolicy,
    ToolCostPolicy,
)

ToolsBackendName = Literal["none", "mcp"]
ToolsSalienceName = Literal["repeat", "off"]

DEFAULT_SPAWN_COST = MAX_TOOL_DISPATCHES // 4


class ToolsConfig(BaseSettings):
    """Whether the cortex can call tools over MCP (ADR-0009, refinements addendum)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_", env_nested_delimiter="__")

    backend: ToolsBackendName = "none"
    endpoint: str = ""
    endpoints: dict[str, str] = {}
    allow: dict[str, tuple[str, ...]] = {}
    on_unavailable: Literal["fail", "skip"] = "fail"
    gated: tuple[str, ...] = (ESCALATE_TOOL_NAME, "send_email")
    gate_reasons: dict[str, str] = {}
    costs: dict[str, int] = {}
    salience: ToolsSalienceName = "repeat"
    salience_limit: int = MAX_IDENTICAL_DISPATCHES

    @model_validator(mode="after")
    def _mcp_needs_unambiguous_endpoints(self) -> "ToolsConfig":
        if self.backend == "mcp" and not (self.endpoint or self.endpoints):
            msg = (
                "CORTEX_TOOLS_ENDPOINT or CORTEX_TOOLS_ENDPOINTS__<name> is required "
                "when CORTEX_TOOLS_BACKEND=mcp"
            )
            raise ValueError(msg)
        if self.endpoint and self.endpoints:
            msg = "set CORTEX_TOOLS_ENDPOINT or CORTEX_TOOLS_ENDPOINTS__<name>, not both"
            raise ValueError(msg)
        if unmatched := set(self.allow) - set(self.named_endpoints):
            msg = f"CORTEX_TOOLS_ALLOW names no configured endpoint: {sorted(unmatched)}"
            raise ValueError(msg)
        if bad := sorted(n for n, c in self.costs.items() if not 1 <= c <= MAX_TOOL_DISPATCHES):
            msg = f"CORTEX_TOOLS_COSTS must be 1..{MAX_TOOL_DISPATCHES}: {bad}"
            raise ValueError(msg)
        # A blank gate reason would render an empty confirm card line, a consent surface that
        # no longer says what is being approved. Misconfiguration fails at boot, not on screen.
        if blank := sorted(n for n, r in self.gate_reasons.items() if not r.strip()):
            msg = f"CORTEX_TOOLS_GATE_REASONS must be non-empty text: {blank}"
            raise ValueError(msg)
        if self.salience_limit < 1:
            msg = f"CORTEX_TOOLS_SALIENCE_LIMIT must be positive: {self.salience_limit}"
            raise ValueError(msg)
        return self

    @property
    def cost_policy(self) -> ToolCostPolicy:
        """The effective prices as the core's policy value (ADR-0009 cost addendum)."""
        return ToolCostPolicy({SPAWN_TOOL_NAME: DEFAULT_SPAWN_COST} | self.costs)

    @property
    def gate_reason_map(self) -> dict[str, str]:
        """The effective per-tool confirm-card reasons (ADR-0030 decision 1)."""
        return {ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON} | self.gate_reasons

    @property
    def salience_policy(self) -> SaliencePolicy:
        """The core policy deciding which calls a tool loop dispatches (salience addendum)."""
        if self.salience != "repeat":
            return ALWAYS_SALIENT
        return RepeatSalience(limit=self.salience_limit)

    @property
    def dispatch_policy(self) -> DispatchPolicy:
        """The four composition-root declarations about dispatching, as one value."""
        return DispatchPolicy(
            gated_names=self.gated,
            costs=self.cost_policy,
            salience=self.salience_policy,
            gate_reasons=self.gate_reason_map,
        )

    @property
    def named_endpoints(self) -> dict[str, str]:
        """Every configured endpoint by name, sorted by name so precedence is deterministic."""
        if self.endpoints:
            return dict(sorted(self.endpoints.items()))
        if self.endpoint:
            return {"default": self.endpoint}
        return {}
