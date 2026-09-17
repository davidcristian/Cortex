"""Tool-dispatch configuration: env-driven, root-read only."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    ALWAYS_SALIENT,
    DEFAULT_TOOL_CALL_TIMEOUT_S,
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

DEFAULT_SALIENCE: ToolsSalienceName = "repeat"

# A quarter of the turn's dispatch budget, so a turn may delegate four times: one spawn is a
# whole batch of model runs, where the flat price of one would have allowed thirty two batches.
DEFAULT_SPAWN_COST = MAX_TOOL_DISPATCHES // 4


class ToolsConfig(BaseSettings):
    """Whether the cortex can call tools over MCP."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_", env_nested_delimiter="__")

    backend: ToolsBackendName = "none"
    endpoint: str = ""
    endpoints: dict[str, str] = {}
    allow: dict[str, tuple[str, ...]] = {}
    on_unavailable: Literal["fail", "skip"] = "fail"
    gated: tuple[str, ...] = (ESCALATE_TOOL_NAME, "send_email")
    gate_reasons: dict[str, str] = {}
    costs: dict[str, int] = {}
    salience: ToolsSalienceName = DEFAULT_SALIENCE
    salience_limit: int = MAX_IDENTICAL_DISPATCHES
    call_timeout_s: float = Field(default=DEFAULT_TOOL_CALL_TIMEOUT_S, gt=0)
    audit_file: str = ""

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
        # A price outside the range has no visible symptom at runtime: zero or less makes the
        # tool free, and above the budget makes it unaffordable, so its first call closes the
        # turn's budget.
        if bad := sorted(n for n, c in self.costs.items() if not 1 <= c <= MAX_TOOL_DISPATCHES):
            msg = f"CORTEX_TOOLS_COSTS must be 1..{MAX_TOOL_DISPATCHES}: {bad}"
            raise ValueError(msg)
        if blank := sorted(n for n, r in self.gate_reasons.items() if not r.strip()):
            msg = f"CORTEX_TOOLS_GATE_REASONS must be non-empty text: {blank}"
            raise ValueError(msg)
        if self.salience_limit < 1:
            msg = f"CORTEX_TOOLS_SALIENCE_LIMIT must be positive: {self.salience_limit}"
            raise ValueError(msg)
        return self

    @property
    def cost_policy(self) -> ToolCostPolicy:
        """The effective prices as the core's policy value."""
        # The built-in prices are merged under the user's rather than being the field's default,
        # because a nested-dict env key replaces the whole mapping: pricing one filesystem tool
        # would otherwise drop ``spawn_subagents`` back to one with nothing reporting it.
        return ToolCostPolicy({SPAWN_TOOL_NAME: DEFAULT_SPAWN_COST} | self.costs)

    @property
    def gate_reason_map(self) -> dict[str, str]:
        """The effective per-tool confirm-card reasons."""
        return {ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON} | self.gate_reasons

    @property
    def salience_policy(self) -> SaliencePolicy:
        """The core policy deciding which calls a tool loop dispatches."""
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
