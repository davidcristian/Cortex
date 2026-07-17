"""Dispatch one tool call and audit it. It is the only path a tool runs through (ADR-0009/0013).

``ToolDispatcher`` is a stateless function over the ``ToolRegistry`` + ``ToolAuditSink``
ports, like ``MemoryRecaller`` over the memory ports: it holds no state, so a restart or
model swap between calls changes nothing (the one hard rule). Its contract is that **every**
dispatch writes exactly one audit record, so a dispatch failure becomes an ``is_error``
``ToolResult`` (the model is told and can recover), never an unaudited crash.

It is also the capability gate (ADR-0013, table revised by ADR-0022 decision 2): a ``gated``
(irreversible/outbound) tool runs only with the human's out-of-band approval via the
``Confirmer`` port. On a turn that has read untrusted content (``tainted``) it never
runs at all, the confirmer deliberately unconsulted: an action demanded by injected content
must not be merely a confirm-away. Every block returns an error result **without invoking
the tool** (``DENIED_MSG`` for the taint block, ``USER_DECLINED_MSG`` for a declined or
unreachable confirmation, the fail-closed no-confirmer default included, and a
``DispatchRefusal`` message when the caller refused the call before it got here) and is audited.
The approval is the human's, reached out of band, never the (possibly jailbroken) model's.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, Confirmer, ToolAuditSink, ToolRegistry
from cortex_core.tool_budget import UNIFORM_COST, ToolCostPolicy
from cortex_core.tool_round import MAX_CALLS_PER_ROUND
from cortex_core.tool_salience import REPEAT_SALIENCE, SaliencePolicy
from cortex_core.tools import (
    UNSTAMPED,
    ConfirmationRequest,
    ToolCall,
    ToolInvocation,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.untrusted import DENIED_MSG, USER_DECLINED_MSG

# Why confirmation is required, shown verbatim to the user by the overlay (ADR-0022). The
# default when the policy names no per-tool reason (ADR-0030 decision 1): true for the outbound
# and irreversible tools, and overridden where it would be false (the escalate card).
_GATE_REASON = "this action is outbound or irreversible and runs only with your approval"

# The result content fed back when the caller's dispatch budget is spent (ADR-0009 budget
# addendum). Phrased so the model stops calling tools and answers with what it already has,
# rather than retrying the same call into a bound that cannot move within the loop.
BUDGET_EXHAUSTED_MSG = (
    "REFUSED: this turn has reached its limit on tool calls, so the tool was not run. Do not "
    "retry this or any other tool call. Answer the user with the information you already have, "
    "and say that you stopped short if the answer is incomplete."
)

# The result content fed back when the caller's salience policy recognized a repeat (ADR-0009
# salience addendum). Unlike the budget message this one does **not** say to stop calling tools:
# only this call is refused, and a different one is still welcome. It points at the earlier
# result rather than describing it, since that result is already in the conversation above.
REDUNDANT_MSG = (
    "REFUSED: this exact tool call has already run in this turn, so it was not run again. Its "
    "result is already in this conversation above. Use that result, or call a different tool, "
    "but do not repeat this call."
)

# The result content fed back on the one slot a truncated round keeps (ADR-0009 round-cap
# addendum). It names the cap, as the spawn batch cap's error does, because a bound the model
# can restate is one it can obey; and it invites the next reply rather than ending tool use,
# since the calls it dropped may be work the turn still needs.
ROUND_OVERSIZED_MSG = (
    f"REFUSED: one reply may ask for at most {MAX_CALLS_PER_ROUND} tool calls at once. This "
    "reply asked for more, so this call and every call after it were dropped without running. "
    "The calls before it did run, and their results are in this conversation above. Ask for "
    "whatever you still need in your next reply, a few calls at a time."
)


class DispatchRefusal(Enum):
    """Why the caller refused a call before it could run, and what the model is told.

    The member's value **is** the model-facing message, so a new reason cannot be added without
    writing one, and ``dispatch`` keeps a single refusal branch however many reasons appear. A
    reason rather than one boolean per bound (ADR-0009 salience addendum): parallel keywords all
    meaning "refuse this and say why" is the shape the ``TurnStamp`` widening already rejected.
    """

    BUDGET = BUDGET_EXHAUSTED_MSG
    REDUNDANT = REDUNDANT_MSG
    ROUND_OVERSIZED = ROUND_OVERSIZED_MSG

    @property
    def message(self) -> str:
        """The refusal text fed back to the model as the call's result."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class DispatchPolicy:
    """What the composition root declares about dispatching, in one value.

    Four declarations that a sidecar must never make about itself: which tools are ``gated``
    (ADR-0022, the authoritative backstop the advertised flag is OR-ed with), what each one
    ``costs`` against the caller's budget (ADR-0009 cost addendum), which calls are worth
    running at all (``salience``, ADR-0009 salience addendum), and what a gated tool's confirm
    card tells the user (``gate_reasons``, ADR-0030 decision 1: a per-tool reason for the card
    where the generic "outbound or irreversible" text would be false, e.g. the escalate card
    naming the model swap; unnamed tools keep the generic reason). They travel together because
    they are one category, and because ruff's argument ceiling left no room for a seventh
    parameter on either the dispatcher or its builder: bundling only two would have reached the
    ceiling again on the next declaration.

    ``gated_names`` is frozen at construction like ``ToolCostPolicy`` freezes its prices, and
    ``gate_reasons`` is copied into a read-only proxy for the same reason: whoever built the
    policy cannot keep editing the gate set or the card text afterwards.
    """

    gated_names: Collection[str] = ()
    costs: ToolCostPolicy = UNIFORM_COST
    salience: SaliencePolicy = REPEAT_SALIENCE
    gate_reasons: Mapping[str, str] = field(default_factory=dict[str, str])

    def __post_init__(self) -> None:
        object.__setattr__(self, "gated_names", frozenset(self.gated_names))
        object.__setattr__(self, "gate_reasons", MappingProxyType(dict(self.gate_reasons)))


# The policy a dispatcher gets unless the composition root passes one: nothing gated, every tool
# priced at one, and repeats refused. Only the last is a behavior the loop had to opt into
# before; the other two are the pre-policy defaults restated.
DEFAULT_DISPATCH_POLICY = DispatchPolicy()


class ToolDispatcher:
    """Run a tool call through the registry, gating and recording one audit line per dispatch.

    Also the turn's single tool gateway: ``describe_tools`` passes through to the registry
    so the engine advertises the same tools it can dispatch.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        audit: ToolAuditSink,
        clock: Clock,
        *,
        confirmer: Confirmer | None = None,
        policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
    ) -> None:
        self._registry = registry
        self._audit = audit
        self._clock = clock
        self._confirmer = confirmer
        # Everything the composition root declares about dispatching: the authoritative gated
        # set (ADR-0022), what each tool spends of the caller's budget (ADR-0009 cost addendum),
        # and which calls are worth running (ADR-0009 salience addendum). None of the three is
        # ever read off a `ToolSpec`, so a sidecar can neither ungate, price, nor un-refuse
        # itself. The dispatcher decides none of them either: the loop asks, then states its
        # verdict as a `DispatchRefusal`, and the dispatcher's job is to make that verdict
        # audited like any other outcome.
        self._policy = policy

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The tools available to advertise to the model (delegates to the registry)."""
        return await self._registry.describe_tools()

    def cost_of(self, name: str) -> int:
        """What dispatching ``name`` spends of the caller's budget (ADR-0009 cost addendum).

        Answered for any name, advertised or not, so the loop can charge a call before knowing
        whether the registry will accept it: an unadvertised name still reaches ``dispatch``
        and still costs a round trip, so pricing it at the default rather than free keeps a
        model that invents names from dispatching without limit.
        """
        return self._policy.costs.cost_of(name)

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool:
        """Whether ``call`` is worth dispatching, given what the caller has already run.

        ``dispatched`` is the caller's own calls grouped by round (ADR-0009 salience addendum),
        which is why the loop keeps it rather than the dispatcher: a repeat is redundant against
        the message list that already holds its answer, and two loops sharing this dispatcher
        (a subagent and the cortex that spawned it) hold different ones. The policy is stateless,
        so sharing it costs nothing and per-loop scoping falls out.
        """
        return self._policy.salience.admits(call, dispatched)

    async def dispatch(
        self,
        call: ToolCall,
        *,
        stamp: TurnStamp = UNSTAMPED,
        gated: bool = False,
        refusal: DispatchRefusal | None = None,
    ) -> ToolResult:
        """Invoke ``call``, audit the outcome, and return the result the model consumes.

        ``refusal`` is the caller's statement that the call must not run: its budget is spent
        (ADR-0009 budget addendum) or its salience policy recognized a repeat (salience
        addendum). The refusal itself belongs here so it is audited like every other dispatch,
        and it is checked **first**, ahead of the gate. Ordering it after would let a model
        emitting hundreds of gated calls put a confirmation prompt in front of the user for
        each one before either bound refused any, turning a spam bound into a flood.

        The gate (ADR-0022 decision 2): a gated tool on a tainted turn is blocked outright
        (``DENIED_MSG``, the confirmer never consulted); on an untainted turn it runs only
        with the user's approval (``USER_DECLINED_MSG`` otherwise, and a missing confirmer
        denies, fail-closed). Every block returns without invoking the tool. Otherwise a
        ``ToolError`` from the registry (unknown tool, transport) is caught and returned as
        an ``is_error`` result. The loop keeps going and the model sees the failure.
        """
        # Overwrite the call's stamp with the turn's (ADR-0018/0027): provenance for built-ins
        # that spawn further work, never authority. The gate below keeps using the explicit
        # ``stamp`` argument, so a model-forged stamp is discarded and feeds nothing.
        call = replace(call, stamp=stamp)
        if refusal is not None:
            refused = ToolResult(
                call_id=call.id,
                content=refusal.message,
                is_error=True,
                trust=Trust.TRUSTED,
            )
            return await self._audited(call, refused)
        # The advertised flag OR the authoritative gated set (ADR-0022): a gated tool a flaky
        # sidecar hid from this turn's advertisement snapshot is still gated here.
        gated = gated or call.name in self._policy.gated_names
        if gated:
            if stamp.tainted:
                blocked = ToolResult(
                    call_id=call.id, content=DENIED_MSG, is_error=True, trust=Trust.TRUSTED
                )
                return await self._audited(call, blocked)
            if not await self._confirmed(call):
                declined = ToolResult(
                    call_id=call.id, content=USER_DECLINED_MSG, is_error=True, trust=Trust.TRUSTED
                )
                return await self._audited(call, declined)
        try:
            result = await self._registry.invoke(call)
        except ToolError as err:
            # Our own dispatch-error message (not external content) is trusted, so it neither
            # frames as data nor taints the turn.
            result = ToolResult(
                call_id=call.id, content=str(err), is_error=True, trust=Trust.TRUSTED
            )
        return await self._audited(call, result)

    async def _confirmed(self, call: ToolCall) -> bool:
        """Ask the confirmer to approve a gated call; a missing confirmer denies (fail-closed).

        The reason shown on the card is the policy's per-tool text when one is declared
        (ADR-0030 decision 1) and the generic gate reason otherwise, so the card never states
        "outbound or irreversible" about an action where that would be false.
        """
        if self._confirmer is None:
            return False
        request = ConfirmationRequest(
            tool_name=call.name,
            arguments=call.arguments,
            reason=self._policy.gate_reasons.get(call.name, _GATE_REASON),
        )
        return await self._confirmer.confirm(request)

    async def _audited(self, call: ToolCall, result: ToolResult) -> ToolResult:
        """Record one audit line (with the result's provenance) and return the result."""
        await self._audit.record(
            ToolInvocation(
                name=call.name,
                arguments=call.arguments,
                ok=not result.is_error,
                detail=result.content,
                at=self._clock.now(),
                trust=result.trust,
            )
        )
        return result
