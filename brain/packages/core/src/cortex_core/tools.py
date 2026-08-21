"""Tool domain values: what a tool is, a call to one, its result, and the audit record.

Pure data, no I/O and no ``ports`` import. That lets ``ports.py`` depend on these without a
cycle, exactly as ``memory.py`` is depended on. ``arguments``/``parameters`` carry arbitrary
JSON (a tool's schema and a model's call args are open-shaped), so ``Any`` here is the
justified kind: the boundary is genuinely dynamic and the value is round-tripped, never
introspected by the core. The exceptions to "values only" are the live handles a
``TurnStamp`` carries (the ``DispatchBudget``, the ``ProgressSink``, and the ``EscalationSlot``)
rather than values; ``tool_budget``, ``provenance``, and ``progress`` (the stamp's collaborators)
import nothing but the standard library (``progress`` transitively, through ``events``), and the
slot's type is imported for typing only (``handoff`` reaches ``untrusted``, which depends on this
module), so depending on them keeps this module port-free and cycle-free at runtime.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from cortex_core.images import ImagePart
from cortex_core.progress import ProgressSink
from cortex_core.provenance import Provenance
from cortex_core.tool_budget import DispatchBudget

if TYPE_CHECKING:
    from cortex_core.handoff import EscalationSlot


class Trust(Enum):
    """The provenance of a tool result's content (ADR-0013): is it data or instructions?

    ``UNTRUSTED`` content comes from a third party (file contents, email bodies, later web
    pages and screen captures) and must be framed as inert data the model never obeys.
    ``TRUSTED`` content is system-generated (a built-in's status string). The distinction is
    binary because the boundary only ever acts on that one question. The default everywhere is
    ``UNTRUSTED`` (fail-closed): content that reaches the model without an explicit trust stamp
    is framed as hostile, never silently trusted.
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool advertised to the model: its name, a one-line purpose, and its JSON-Schema args.

    ``parameters`` is the JSON Schema the model fills to call the tool, passed through to the
    model verbatim and never interpreted by the core. ``gated`` marks an irreversible/outbound
    action (email-write, later OS actions) that requires explicit confirmation once the turn
    has read untrusted content (ADR-0013); no tool sets it today (all reads are read-only).
    """

    name: str
    description: str
    parameters: Mapping[str, Any]
    gated: bool = False


@dataclass(frozen=True, slots=True)
class TurnStamp:
    """What the dispatching turn hands the call, stamped on at dispatch time (ADR-0027).

    ``session_id`` is the originating chat (``""`` when the dispatch has none: an
    unattributed caller); ``turn_id`` the conversation turn the dispatch was made for and
    ``task_id`` the subagent task it was made inside, the two identities the audit trail
    names the work by (ADR-0009 named-work addendum; each ``""`` when there is none, so a
    turn's own dispatch carries no task and a ticker-rooted subagent's carries no turn);
    ``tainted`` whether the turn had read untrusted content
    at dispatch time; ``sources`` which sources that content came from (ADR-0027 addendum),
    the structured provenance behind the bit; ``budget`` the turn's shared dispatch allowance
    (``None`` when the caller runs no tool loop, e.g. the schedule ticker); ``progress`` the
    stream's side channel for the ephemeral progress a suspended turn cannot yield (``None``
    when the dispatch has no overlay stream, e.g. the ticker, ADR-0010). One frozen value
    rather than parallel keywords, which is what let ``sources`` land without touching a single
    call site. A field joins only with a consumer, or a designed one: ``sources`` is captured
    live (the ledger dies with the turn) for consumers that are decisions of their own, a
    confirmation card that names its source and per-provenance eviction.

    Originally the turn's *provenance* alone. ``budget`` widened that to what the turn hands
    down to work this call spawns (which ``tainted`` already was in practice), ``progress``
    to where that spawned work surfaces its steps, and ``escalation`` (ADR-0030) to the turn's
    handoff slot, which the ``escalate_to_brain`` built-in writes its brief into (``None`` for
    an escalation-less turn or a turn-less caller like the ticker). All three are live shared
    handles rather than values, so all are excluded from equality: two dispatches of the same
    turn stay comparable, and no caller can mistake one pool (or one stream's sink, or one
    turn's slot) for another (ADR-0009 turn-wide addendum, ADR-0010 progress addendum,
    ADR-0030 decision 2).
    """

    session_id: str = ""
    turn_id: str = ""
    task_id: str = ""
    tainted: bool = False
    sources: tuple[Provenance, ...] = ()
    budget: DispatchBudget | None = field(default=None, compare=False)
    progress: ProgressSink | None = field(default=None, compare=False)
    escalation: "EscalationSlot | None" = field(default=None, compare=False)


# The unattributed default stamp: no originating session, no taint. A named constant
# (not a call in a default) so signatures can default to it under the lint gate.
UNSTAMPED = TurnStamp()


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A request to run one tool: the model's chosen ``name`` and ``arguments``.

    ``id`` correlates this call with its ``ToolResult`` across the tool loop; the model (or
    the loop, for a fake backend) assigns it. ``stamp`` is never the model's to set: the
    dispatcher overwrites it at dispatch time with the calling turn's ``TurnStamp``
    (ADR-0018/0027), so a built-in that spawns further work (``spawn_subagents``, the
    schedule tools) can propagate provenance. The stamp is transient (the loop persists the
    unstamped calls) and it never feeds the ADR-0013 gate, which uses the dispatcher's
    explicit argument.
    """

    id: str
    name: str
    arguments: Mapping[str, Any]
    stamp: TurnStamp = UNSTAMPED


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of one ``ToolCall``: ``content`` fed back to the model, ``is_error`` set
    when the tool (or its dispatch) failed. The model is told, so it can recover.

    ``trust`` is the provenance of ``content`` (ADR-0013), defaulting ``UNTRUSTED`` so any
    result reaching the loop without an explicit stamp is framed as data. A generic registry
    (MCP, the in-memory twin) leaves the default; only a built-in returning system-generated
    bytes stamps ``TRUSTED``.

    ``source`` is a source the *result* declared for its own ``content`` (ADR-0027 addendum): a
    sidecar-declared sender or locator that the MCP adapter parsed from the result's ``_meta`` side
    channel, ``None`` when it declared none (every result today but the email reader's). It is a
    **claimed** ``Provenance`` (``SourceKind.attested`` is ``False``): the declaration is
    attacker-influenceable, so the ledger notes it beside the attested tool source and it can only
    ever annotate, never relax taint. It rides beside ``content``, not inside it, so a declaration
    never disturbs the string the model reads.

    ``images`` (ADR-0029) carries pixels a tool produced, and rides **beside** ``content``
    rather than inside it for the same reason ``source`` does, only more so: ``content`` is what
    the audit sink logs verbatim on failure, what URL extraction scans, and what the untrusted
    fence wraps. Keeping all three text-only means a failed capture can never put megabytes of
    image into the audit log, and no fence is ever asked to bracket something it cannot.
    """

    call_id: str
    content: str
    is_error: bool = False
    trust: Trust = Trust.UNTRUSTED
    source: Provenance | None = None
    images: tuple[ImagePart, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """One line of the audit trail: every dispatched call is recorded, success or failure.

    ``ok`` is the negation of the result's ``is_error``; ``detail`` is the result content or
    the error message; ``trust`` records whether the call returned untrusted content (the
    provenance trail, ADR-0013); ``at`` must be timezone-aware (the audit outlives the process).

    ``session_id``, ``turn_id`` and ``task_id`` are what the line names the work by (ADR-0009
    named-work addendum), copied off the dispatch's ``TurnStamp``: the originating chat, the
    conversation turn, and the subagent task the call was made inside. Each is ``""`` when the
    dispatch had none, so an unattributed caller records absence rather than a borrowed id.
    They are the stamp's *identities* and not the stamp itself, because the stamp also carries
    live handles (the turn's pool, its progress channel, its handoff slot) and this record is a
    value that outlives the process that wrote it: a durable line holding a live pool is a line
    no sink could ever write down.
    """

    name: str
    arguments: Mapping[str, Any]
    ok: bool
    detail: str
    at: datetime
    trust: Trust = Trust.UNTRUSTED
    session_id: str = ""
    turn_id: str = ""
    task_id: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "ToolInvocation.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """A request for out-of-band user confirmation of a gated tool call (ADR-0013/0022).

    Built by the dispatcher when a ``gated`` tool is called on an **untainted** turn (a tainted
    turn's gated call is denied outright, never confirmed per ADR-0022): ``tool_name``/``arguments``
    name the action and ``reason`` says why confirmation is required, so the overlay can show the
    user what they are approving. The ``Confirmer`` port answers it; the model never does, since
    confirmation is the human's, out of band.
    """

    tool_name: str
    arguments: Mapping[str, Any]
    reason: str
