"""Tool-dispatch configuration (ADR-0009): env-driven, root-read only.

Its own module per the ``config_schedule.py`` split precedent (``config.py`` hit its line cap
as the third dispatch declaration landed); same rules apply. It is read exclusively by the
composition root, and everything below the edge receives plain values, which here means the one
``DispatchPolicy`` every ``ToolDispatcher`` in the process is built from: what is gated, what
each tool costs, and which calls are worth dispatching at all.
"""

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

# Which salience rule a loop runs under when nothing overrides it. Declared here rather than
# written inline in the field below, because the base compose file ships the same answer as a
# substitution default and `scripts/crosscheck.py` can only hold that to a declaration it can read.
# It stays distinct from the ``"repeat"`` the policy builder compares against: that comparison asks
# which rule was picked rather than which one ships, and folding the two would make retuning the
# default retarget the branch with nothing reporting it.
DEFAULT_SALIENCE: ToolsSalienceName = "repeat"

# What one `spawn_subagents` dispatch spends of a loop's dispatch budget (ADR-0009 cost
# addendum). A quarter of `MAX_TOOL_DISPATCHES`, so a turn may delegate four times: the tool
# takes a batch of instructions, so four dispatches is ample fan-out, while the flat price
# would have allowed thirty two batches of concurrent model runs from one turn. Priced here
# rather than in the core because what a spawn costs is a property of this deployment's
# hardware rather than of the tool.
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
    fails tool listing; ``skip`` serves the healthy sidecars and logs the dead one on every
    walk (ADR-0009 degraded-mode addendum), so a degraded stack still says so on each walk.
    ``CORTEX_TOOLS_GATED`` (a JSON name list, ADR-0022) names the tools the brain declares
    outbound/irreversible/disruptive: the composition root stamps remote ones ``gated``, so the
    dispatcher's confirm gate covers them and subagents never see them. The default covers
    ``send_email``, so enabling the email sidecar's write path without touching gating
    config still gates it (fail-closed pairing), and ``escalate_to_brain`` (ADR-0030), the
    dispatcher-side backstop behind that built-in's own always-gated advertised flag; an
    empty list disables the overlay (the escalate spec stays gated regardless).
    ``CORTEX_TOOLS_GATE_REASONS__<name>=<text>`` (ADR-0030 decision 1) sets the confirm card's
    reason for one gated tool, where the generic "outbound or irreversible" line would be
    false; unnamed tools keep the generic reason, a blank text fails at boot, and
    ``gate_reason_map`` merges the built-in ``escalate_to_brain`` reason (the app-authored
    model-swap text) under whatever the user set, the ``cost_policy`` merge precedent.
    ``CORTEX_TOOLS_COSTS__<name>=<int>`` prices a tool against the loop's dispatch budget
    (ADR-0009 cost addendum), one per key so layered compose overrides each contribute the
    price of the tool they enable, and anything unpriced costs one. ``cost_policy`` is the
    effective result: it merges the built-in prices under whatever the user set. Built in is
    ``spawn_subagents``, the one wired tool whose single dispatch fans out into a batch of
    model runs and which no confirmation gate bounds; ``send_email`` is deliberately unpriced,
    because every send already needs the user's approval and a human saying yes thirty two
    times is the tighter bound. A price outside ``1..MAX_TOOL_DISPATCHES`` fails at boot.
    ``CORTEX_TOOLS_SALIENCE`` picks which calls a tool loop dispatches (ADR-0009 salience
    addendum): ``repeat`` (the default) filters out a call the loop has already made, and
    ``off`` restores the unfiltered loop. ``CORTEX_TOOLS_SALIENCE_LIMIT`` retunes how many times
    one identical call may be dispatched across a ``repeat`` loop, for the deployment where the
    shipped two proves wrong; it defaults to ``MAX_IDENTICAL_DISPATCHES``, the once-per-round
    clause is absolute and no number moves it, a value below 1 fails at boot, and the knob is
    inert under ``off``. ``dispatch_policy`` bundles all three declarations, which is the one
    value the dispatcher and its builders take.
    ``CORTEX_TOOLS_CALL_TIMEOUT_S`` (ADR-0009 bound addendum) is how long one call on a sidecar
    may take before the brain stops waiting for it, a listing and an invoke alike. It is spent by
    the ``BoundedToolRegistry`` each endpoint is wrapped in, so a wedged sidecar fails one call
    instead of holding a turn open, and it is the one declaration here that is inert under
    ``none``, there being no sidecar to bound.
    """

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
        # A price outside 1..budget is a misconfiguration with no visible symptom: zero or less
        # makes the tool free, so the budget stops bounding the one tool a user cared enough to
        # configure; above the budget makes it permanently unaffordable, so it never runs and the
        # first call closes the turn's budget. Both would surface as puzzling runtime behavior, so
        # they fail at boot instead.
        if bad := sorted(n for n, c in self.costs.items() if not 1 <= c <= MAX_TOOL_DISPATCHES):
            msg = f"CORTEX_TOOLS_COSTS must be 1..{MAX_TOOL_DISPATCHES}: {bad}"
            raise ValueError(msg)
        # A blank gate reason would render an empty confirm card line, leaving a consent surface
        # that no longer says what is being approved, so it fails at boot rather than on screen.
        if blank := sorted(n for n, r in self.gate_reasons.items() if not r.strip()):
            msg = f"CORTEX_TOOLS_GATE_REASONS must be non-empty text: {blank}"
            raise ValueError(msg)
        # A limit below one rejects every call including the first, which the loop reports to the
        # model as refusals it cannot act on rather than as a failure: a hole nothing announces,
        # and exactly the shape `RepeatSalience` already rejects at construction. Restating it here
        # moves the rejection to boot, where the operator who typed the number is still watching,
        # instead of to the first property read. There is deliberately no ceiling: a limit at or
        # above `MAX_TOOL_STEPS` never binds, which is a knob doing nothing rather than a hole, and
        # it still says something `off` does not, since the once-per-round clause stays.
        if self.salience_limit < 1:
            msg = f"CORTEX_TOOLS_SALIENCE_LIMIT must be positive: {self.salience_limit}"
            raise ValueError(msg)
        return self

    @property
    def cost_policy(self) -> ToolCostPolicy:
        """The effective prices as the core's policy value (ADR-0009 cost addendum).

        The built-in prices are merged under the user's, rather than being the field's default,
        because a nested-dict env key replaces the whole mapping: pricing one filesystem tool via
        `CORTEX_TOOLS_COSTS__READ_FILE` would otherwise drop `spawn_subagents` back to one with
        nothing reporting it, un-pricing the fan-out tool as a side effect of an unrelated knob.
        Restating a built-in price still overrides it, which is deliberate.
        """
        return ToolCostPolicy({SPAWN_TOOL_NAME: DEFAULT_SPAWN_COST} | self.costs)

    @property
    def gate_reason_map(self) -> dict[str, str]:
        """The effective per-tool confirm-card reasons (ADR-0030 decision 1).

        The built-in ``escalate_to_brain`` reason is merged under the user's for the same reason
        ``cost_policy`` merges: a nested-dict env key replaces the whole mapping, so setting a
        reason for one tool must not drop the escalate card back to the generic "outbound or
        irreversible" text, which is false for a model swap, with nothing reporting the change.
        Restating the built-in still overrides it, which is deliberate.
        """
        return {ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON} | self.gate_reasons

    @property
    def salience_policy(self) -> SaliencePolicy:
        """The core policy deciding which calls a tool loop dispatches (salience addendum).

        The core takes a policy object; the composition root maps the string, the
        `record_tainted_memory` precedent. ``off`` is the pre-policy loop exactly, and the
        limit is inert under it because `AlwaysSalient` counts nothing. The shared
        `REPEAT_SALIENCE` singleton is not returned even when the limit is its default: a
        branch on whether the number happens to match would be an untested path bought for one
        object, and the policy is a frozen dataclass, so a fresh one compares equal anyway.
        """
        if self.salience != "repeat":
            return ALWAYS_SALIENT
        return RepeatSalience(limit=self.salience_limit)

    @property
    def dispatch_policy(self) -> DispatchPolicy:
        """The four composition-root declarations about dispatching, as one value.

        What every `ToolDispatcher` in the process is built with: the gate backstop, the prices,
        the salience rule (ADR-0009 salience addendum decision 10), and the per-tool confirm-card
        reasons (ADR-0030 decision 1). Bundled because ruff's argument ceiling left no room for a
        seventh builder parameter, and because a sidecar may claim none of the four for itself.
        """
        return DispatchPolicy(
            gated_names=self.gated,
            costs=self.cost_policy,
            salience=self.salience_policy,
            gate_reasons=self.gate_reason_map,
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
