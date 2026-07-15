"""Tool-dispatch configuration (ADR-0009): env-driven, root-read only.

Its own module per the ``config_schedule.py`` split precedent (``config.py`` hit its line cap
as the third dispatch declaration landed); same rules apply. It is read exclusively by the
composition root, and everything below the edge receives plain values, which here means the one
``DispatchPolicy`` every ``ToolDispatcher`` in the process is built from: what is gated, what
each tool costs, and which calls are worth dispatching at all.
"""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    ALWAYS_SALIENT,
    MAX_TOOL_DISPATCHES,
    REPEAT_SALIENCE,
    SPAWN_TOOL_NAME,
    DispatchPolicy,
    SaliencePolicy,
    ToolCostPolicy,
)

ToolsBackendName = Literal["none", "mcp"]
ToolsSalienceName = Literal["repeat", "off"]

# What one `spawn_subagents` dispatch spends of a loop's dispatch budget (ADR-0009 cost
# addendum). A quarter of `MAX_TOOL_DISPATCHES`, so a turn may delegate four times: the tool
# takes a *batch* of instructions, so four dispatches is ample fan-out, while the flat price
# would have allowed thirty two batches of concurrent model runs from one turn. Priced here
# rather than in the core because what a spawn costs is a property of this deployment's
# hardware, not of the tool.
DEFAULT_SPAWN_COST = MAX_TOOL_DISPATCHES // 4


class ToolsConfig(BaseSettings):
    """Whether the cortex can call tools over MCP (ADR-0009, refinements addendum).

    ``none`` (the default) disables tools. CI and the no-GPU dev loop run with no MCP server.
    ``mcp`` enables the MCP client and requires tool-server endpoint(s), one of two forms:
    the singular ``endpoint`` (one streamable-http URL), or one ``endpoints`` entry per
    sidecar (``CORTEX_TOOLS_ENDPOINTS__<name>=<url>``), so layered compose overrides each
    contribute their own key and coexist. ``CORTEX_TOOLS_ALLOW__<name>=<JSON name list>``
    optionally restricts what ``<name>`` advertises (the read-only filesystem allowlist).
    Setting both forms is ambiguous and rejected, as is an allowlist naming no endpoint.
    ``CORTEX_TOOLS_ON_UNAVAILABLE`` picks the dead-sidecar policy: ``fail`` (the default)
    fails tool listing loudly; ``skip`` serves the healthy sidecars and logs the dead one
    on every walk (ADR-0009 degraded-mode addendum), degraded but never silent.
    ``CORTEX_TOOLS_GATED`` (a JSON name list, ADR-0022) names the remote tools the brain
    declares outbound/irreversible: the composition root stamps them ``gated``, so the
    dispatcher's confirm gate covers them and subagents never see them. The default covers
    ``send_email``, so enabling the email sidecar's write path without touching gating
    config still gates it (fail-closed pairing); an empty list disables the overlay.
    ``CORTEX_TOOLS_COSTS__<name>=<int>`` prices a tool against the loop's dispatch budget
    (ADR-0009 cost addendum), one per key so layered compose overrides each contribute the
    price of the tool they enable, and anything unpriced costs one. ``cost_policy`` is the
    effective result: it merges the built-in prices under whatever the user set. Built in is
    ``spawn_subagents``, the one wired tool whose single dispatch fans out into a batch of
    model runs and which no confirmation gate bounds; ``send_email`` is deliberately unpriced,
    because every send already needs the user's approval and a human saying yes thirty two
    times is the tighter bound. A price outside ``1..MAX_TOOL_DISPATCHES`` fails at boot.
    ``CORTEX_TOOLS_SALIENCE`` picks which calls a tool loop bothers dispatching (ADR-0009
    salience addendum): ``repeat`` (the default) refuses a call the loop has already made, and
    ``off`` restores the unfiltered loop. ``dispatch_policy`` bundles all three declarations,
    which is the one value the dispatcher and its builders take.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_", env_nested_delimiter="__")

    backend: ToolsBackendName = "none"
    endpoint: str = ""
    endpoints: dict[str, str] = {}
    allow: dict[str, tuple[str, ...]] = {}
    on_unavailable: Literal["fail", "skip"] = "fail"
    gated: tuple[str, ...] = ("send_email",)
    costs: dict[str, int] = {}
    salience: ToolsSalienceName = "repeat"

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
        # A price outside 1..budget is a misconfiguration that hides rather than announces
        # itself: zero or less makes the tool free, so the budget stops bounding the one tool
        # a user cared enough to configure; above the budget makes it permanently
        # unaffordable, so it never runs and the first call closes the turn's budget. Both
        # would surface as puzzling runtime behavior, so they fail at boot instead.
        if bad := sorted(n for n, c in self.costs.items() if not 1 <= c <= MAX_TOOL_DISPATCHES):
            msg = f"CORTEX_TOOLS_COSTS must be 1..{MAX_TOOL_DISPATCHES}: {bad}"
            raise ValueError(msg)
        return self

    @property
    def cost_policy(self) -> ToolCostPolicy:
        """The effective prices as the core's policy value (ADR-0009 cost addendum).

        The built-in prices are merged **under** the user's, rather than being the field's
        default, because a nested-dict env key replaces the whole mapping: pricing one
        filesystem tool via `CORTEX_TOOLS_COSTS__READ_FILE` would otherwise silently drop
        `spawn_subagents` back to one, un-pricing the fan-out tool as a side effect of an
        unrelated knob. Restating a built-in price still overrides it, which is deliberate.
        """
        return ToolCostPolicy({SPAWN_TOOL_NAME: DEFAULT_SPAWN_COST} | self.costs)

    @property
    def salience_policy(self) -> SaliencePolicy:
        """The core policy deciding which calls a tool loop dispatches (salience addendum).

        The core takes a policy object; the composition root maps the string, the
        `record_tainted_memory` precedent. ``off`` is the pre-policy loop exactly.
        """
        return REPEAT_SALIENCE if self.salience == "repeat" else ALWAYS_SALIENT

    @property
    def dispatch_policy(self) -> DispatchPolicy:
        """The three composition-root declarations about dispatching, as one value.

        What every `ToolDispatcher` in the process is built with: the gate backstop, the prices,
        and the salience rule (ADR-0009 salience addendum decision 10). Bundled because ruff's
        argument ceiling left no room for a seventh builder parameter, and because a sidecar may
        claim none of the three for itself.
        """
        return DispatchPolicy(
            gated_names=self.gated,
            costs=self.cost_policy,
            salience=self.salience_policy,
        )

    @property
    def named_endpoints(self) -> dict[str, str]:
        """Every configured endpoint by name, sorted by name so precedence is deterministic.

        The order fixes the `AggregateToolRegistry` collision policy (first-wins by sorted
        name), independent of env enumeration order. The singular ``endpoint`` becomes the
        sole entry ``default``.
        """
        if self.endpoints:
            return dict(sorted(self.endpoints.items()))
        if self.endpoint:
            return {"default": self.endpoint}
        return {}
