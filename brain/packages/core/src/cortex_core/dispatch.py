"""Dispatch one tool call and audit it."""

import asyncio
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType

from cortex_core.composite import RecordCard, ResultNote, ToolOffer
from cortex_core.errors import ToolError
from cortex_core.log_secrets import REDACTED
from cortex_core.ports import Clock, Confirmer, ToolAuditSink, ToolRegistry
from cortex_core.progress import hold_wait
from cortex_core.tool_budget import UNIFORM_COST, ToolCostPolicy
from cortex_core.tool_round import MAX_CALLS_PER_ROUND
from cortex_core.tool_salience import REPEAT_SALIENCE, SaliencePolicy
from cortex_core.tools import (
    UNSTAMPED,
    ConfirmAnswer,
    ConfirmationRequest,
    ToolCall,
    ToolInvocation,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.untrusted import (
    DENIED_MSG,
    EXPIRED_MSG,
    RECALL_DENIED_MSG,
    RECALL_FORGOTTEN_MSG,
    UNANSWERED_MSG,
    USER_DECLINED_MSG,
)
from cortex_core.waits import USER_ASKED

_CONFIRM_REASON = "this action is outbound or irreversible and runs only with your approval"

CANCELLED_MSG = "cancelled: the turn ended before this call returned"

_UNAPPROVED = {
    ConfirmAnswer.DECLINED: USER_DECLINED_MSG,
    ConfirmAnswer.EXPIRED: EXPIRED_MSG,
    ConfirmAnswer.UNANSWERED: UNANSWERED_MSG,
}

BUDGET_EXHAUSTED_MSG = (
    "REFUSED: this turn has reached its limit on tool calls, so the tool was not run. Do not "
    "retry this or any other tool call. Answer the user with the information you already have, "
    "and say that you stopped short if the answer is incomplete."
)

REDUNDANT_MSG = (
    "REFUSED: this exact tool call has already run in this turn, so it was not run again. Its "
    "result is already in this conversation above. Use that result, or call a different tool, "
    "but do not repeat this call."
)

ALREADY_DECLINED_MSG = (
    "DECLINED: the user already pressed Deny on this exact action in this turn, so it was not "
    "shown to them again and was not performed. Tell the user it was not done because they "
    "declined it. Do not call it again in this turn."
)

UNASKED_MSG = (
    "REFUSED: the person asked you to remember something and did not ask for this action, so it "
    "was not run. If they may want it, ask them in your reply. Do not call it again in this turn."
)

ROUND_OVERSIZED_MSG = (
    f"REFUSED: one reply may ask for at most {MAX_CALLS_PER_ROUND} tool calls at once. This "
    "reply asked for more, so this call and every call after it were dropped without running. "
    "The calls before it did run, and their results are in this conversation above. Ask for "
    "whatever you still need in your next reply, a few calls at a time."
)


class DispatchRefusal(Enum):
    """Why the caller refused a call before it could run, and what the model is told."""

    BUDGET = BUDGET_EXHAUSTED_MSG
    DECLINED = ALREADY_DECLINED_MSG
    REDUNDANT = REDUNDANT_MSG
    ROUND_OVERSIZED = ROUND_OVERSIZED_MSG
    UNASKED = UNASKED_MSG

    @property
    def message(self) -> str:
        """The refusal text fed back to the model as the call's result."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class DispatchPolicy:
    """What the composition root declares about dispatching, in one value."""

    confirm_names: Collection[str] = ()
    costs: ToolCostPolicy = UNIFORM_COST
    salience: SaliencePolicy = REPEAT_SALIENCE
    confirm_reasons: Mapping[str, str] = field(default_factory=dict[str, str])
    record_cards: Mapping[str, RecordCard] = field(default_factory=dict[str, RecordCard])
    offers: Mapping[str, ToolOffer] = field(default_factory=dict[str, ToolOffer])
    private_names: Collection[str] = ()
    notes: Mapping[str, ResultNote] = field(default_factory=dict[str, ResultNote])

    def __post_init__(self) -> None:
        object.__setattr__(self, "confirm_names", frozenset(self.confirm_names))
        object.__setattr__(self, "private_names", frozenset(self.private_names))
        object.__setattr__(self, "confirm_reasons", MappingProxyType(dict(self.confirm_reasons)))
        object.__setattr__(self, "record_cards", MappingProxyType(dict(self.record_cards)))
        object.__setattr__(self, "offers", MappingProxyType(dict(self.offers)))
        object.__setattr__(self, "notes", MappingProxyType(dict(self.notes)))


DEFAULT_DISPATCH_POLICY = DispatchPolicy()


def _blocked_text(stamp: TurnStamp) -> str:
    """What a tainted turn's blocked call tells the model: what tainted it, and what ran since."""
    if not stamp.recalled_only:
        return DENIED_MSG
    return RECALL_FORGOTTEN_MSG if stamp.forgotten else RECALL_DENIED_MSG


class ToolDispatcher:
    """Run a tool call through the registry, ask for confirmation when needed, and audit it."""

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
        self._policy = policy

    @property
    def private_names(self) -> Collection[str]:
        """The tools whose arguments are kept out of every record the brain writes."""
        return self._policy.private_names

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The tools available to advertise to the model (delegates to the registry)."""
        return await self._registry.describe_tools()

    async def withheld(self, session_id: str) -> frozenset[str]:
        """The tools left out of ``session_id``'s list because their ``ToolOffer`` declines."""
        return frozenset(
            [
                name
                for name, offer in self._policy.offers.items()
                if not await offer.offered(session_id)
            ]
        )

    def cost_of(self, name: str) -> int:
        """What dispatching ``name`` costs against the caller's budget."""
        return self._policy.costs.cost_of(name)

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool:
        """Whether ``call`` is worth dispatching, given what the caller has already run."""
        return self._policy.salience.admits(call, dispatched)

    async def dispatch(
        self,
        call: ToolCall,
        *,
        stamp: TurnStamp = UNSTAMPED,
        confirm_required: bool = False,
        refusal: DispatchRefusal | None = None,
    ) -> ToolResult:
        """Invoke ``call``, audit the outcome, and return the result the model consumes."""
        # The caller's stamp replaces whatever the call arrived with, so a model-written stamp
        # is discarded before the taint check reads it.
        call = replace(call, stamp=stamp)
        try:
            result = await self._dispatched(
                call, confirm_required=confirm_required, refusal=refusal
            )
        except asyncio.CancelledError:
            cut = ToolResult(
                call_id=call.id, content=CANCELLED_MSG, is_error=True, trust=Trust.TRUSTED
            )
            await self._audited(call, cut)
            raise
        noted = self._policy.notes.get(call.name)
        # A call refused as unasked leaves the turn kept, so a note saying otherwise would be false.
        if noted is None or refusal is DispatchRefusal.UNASKED:
            return result
        return replace(result, content=f"{result.content} {noted.result_note}")

    async def _dispatched(
        self, call: ToolCall, *, confirm_required: bool, refusal: DispatchRefusal | None
    ) -> ToolResult:
        """Refuse, block, confirm or run ``call``, and audit the result."""
        if refusal is not None:
            refused = ToolResult(
                call_id=call.id,
                content=refusal.message,
                is_error=True,
                trust=Trust.TRUSTED,
            )
            return await self._audited(call, refused)
        # A tool a failing sidecar left out of this turn's list still needs confirmation.
        confirm_required = confirm_required or call.name in self._policy.confirm_names
        if confirm_required:
            card = self._policy.record_cards.get(call.name)
            # A record card shows the brain's own record rather than text the model wrote, so
            # it is shown on a tainted turn too.
            if call.stamp.tainted and card is None:
                blocked = ToolResult(
                    call_id=call.id,
                    content=_blocked_text(call.stamp),
                    is_error=True,
                    trust=Trust.TRUSTED,
                )
                return await self._audited(call, blocked)
            answer = await self._confirmed(call, card)
            if answer is not None and answer is not ConfirmAnswer.APPROVED:
                declined = ToolResult(
                    call_id=call.id,
                    content=_UNAPPROVED[answer],
                    is_error=True,
                    trust=Trust.TRUSTED,
                )
                return await self._audited(call, declined)
        try:
            result = await self._registry.invoke(call)
        except ToolError as err:
            result = ToolResult(
                call_id=call.id, content=str(err), is_error=True, trust=Trust.TRUSTED
            )
        return await self._audited(call, result)

    async def _confirmed(self, call: ToolCall, card: RecordCard | None) -> ConfirmAnswer | None:
        """Ask the confirmer to approve the call, or ``None`` when its card has nothing to ask."""
        reason = self._policy.confirm_reasons.get(call.name, _CONFIRM_REASON)
        if card is not None:
            shown = await card.card(call)
            if shown is None:
                return None
            reason = shown
        if self._confirmer is None:
            return ConfirmAnswer.UNANSWERED
        request = ConfirmationRequest(tool_name=call.name, arguments=call.arguments, reason=reason)
        async with hold_wait(call.stamp.progress, USER_ASKED):
            return await self._confirmer.confirm(request)

    async def _audited(self, call: ToolCall, result: ToolResult) -> ToolResult:
        """Record one audit line (its provenance, the work it was for, the call) and return it."""
        arguments = call.arguments
        if call.name in self._policy.private_names:
            arguments = dict.fromkeys(arguments, REDACTED)
        await self._audit.record(
            ToolInvocation(
                name=call.name,
                arguments=arguments,
                ok=not result.is_error,
                detail=result.content,
                at=self._clock.now(),
                trust=result.trust,
                call_id=call.id,
                session_id=call.stamp.session_id,
                turn_id=call.stamp.turn_id,
                task_id=call.stamp.task_id,
                item_id=call.stamp.item_id,
            )
        )
        return result
