"""The couplings around the brain's own log vocabulary: one name per work identity, everywhere.

One of the data files `crosscheck.py` reads as a single registry, and the tenth part, added the way
`registry.py` was built to take one: a data file plus one line there, with the scan never learning
the registry grew. The subject is the one thing no other part holds, a field NAME rather than a
field's value, and the five names are the ones a brain log line uses to say which work it is about.

**Why a name needs the gate.** Two identities were spelled two ways at once, and neither split was
noticed until a reader needed both halves of one investigation. The first opened the day the recall
trail did and stood for eighteen days, which is most of that trail's life so far.
The recall trail and the rank's two fallbacks named a conversation `session` where six other
modules named the same fact `session_id`, and the schedule ticker named a fired item `reminder_id`
where the audit trail named it `item_id`. Both splits were invisible to every suite, each side
asserting its own line back, and both were paid by a reader at the worst moment: a fire that went
wrong is exactly when the ticker's lines and the tool calls it caused both matter, and `grep`
returned one of the two. The names moved onto one vocabulary, the dispatch stamp's own (ADR-0009
one-vocabulary addendum), and this part is what stops the next line drifting off it again.

**Why the registry and not an import.** `cortex_core.log_fields` declares all five and only the
tool audit spends them as code, that sink being the one place that writes the whole vocabulary out
as a list. Every other line names one identity inside its own `extra=`, and the string an operator
greps is what a reader of that line came for, so the literal stays. That is the same trade the
subagent part already makes for a docstring restating a number: a far side kept legible on purpose
and tied here rather than made to import. The runbooks are the half no import could reach at all,
each telling an operator to grep a field by name, which is the cost the deferred entry named.

**What is deliberately not here.** The Redis codecs spell `session_id`, `turn_id`, `task_id` and
`item_id` as hash keys of their own records. Those are a wire format rather than a log field, and a
record on disk outlives the deployment that wrote it, so the two answers are free to move apart and
must not be tied to each other. Nor is `NotifyRequest.reminder_id`, the seam's name for the message
the body is handed: the ticker's line is the brain's reading of its own work and takes the brain's
name for it, and that the two differ is the decision rather than a drift.

**The swap path is here now, and it needed no sixth name.** Its eleven lines spelled a handoff
`handoff` and a turn `turn`, and the first of those looked like an identity the stamp does not
carry until the mint was read: `EscalationSlot.snapshot` writes `handoff_id=turn_id`, so a handoff
id is the escalating turn's id and those lines were naming a turn all along. They are tied to
`TURN_FIELD` like any other, and the one line that names two turns at once spends the qualified
spelling `active_turn_id`, tied to the same declaration through a template that renders the
qualifier in front of it, so a rename of the family moves the qualified name with it.
"""

from couplings import Constant, Mention, Site

LOG_FIELDS = "brain/packages/core/src/cortex_core/log_fields.py"

BRAIN_PHASE = "brain/packages/core/src/cortex_core/brain_phase.py"
CONVERSE_STREAM = "brain/packages/orchestrator/src/cortex_orchestrator/converse_stream.py"
ENGINE = "brain/packages/core/src/cortex_core/engine.py"
RECALL_AUDIT = "brain/packages/memory/src/cortex_memory/audit.py"
RERANK_JUDGE = "brain/packages/core/src/cortex_core/rerank_judge.py"
RUNNER = "brain/packages/core/src/cortex_core/runner.py"
SCHEDULE_CLAIMS = "brain/packages/session/src/cortex_session/schedule_claims.py"
SUMMARIZING = "brain/packages/core/src/cortex_core/summarizing.py"
SWAP_CONDUCTOR = "brain/packages/core/src/cortex_core/swap_conductor.py"
SWAP_RECOVERY = "brain/packages/core/src/cortex_core/swap_recovery.py"
SWAP_SETTLE = "brain/packages/core/src/cortex_core/swap_settle.py"
TICKER = "brain/packages/orchestrator/src/cortex_orchestrator/ticker.py"
TURN_CONTEXT = "brain/packages/core/src/cortex_core/turn_context.py"
TURN_OUTPUT = "brain/packages/core/src/cortex_core/turn_output.py"

MEMORY_RUNBOOK = "docs/runbooks/memory-pgvector.md"
SCHEDULING_RUNBOOK = "docs/runbooks/scheduling.md"
SWAP_RUNBOOK = "docs/runbooks/model-swap.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"

# How a Python log site writes one of these names: a string key opening an ``extra=`` dict. The
# colon is what keeps the needle a field name rather than any other use of the same word, and it
# is why the mentions below need no further neighbouring text to be a claim about the right line.
FIELD_KEY = '"{value}":'

# How a line naming a SECOND instance of one identity writes the qualified spelling: the same key,
# with the qualifier in front of the family word. Rendered from the same declaration as the plain
# name, so the qualified one cannot be left behind by a rename of the family it belongs to.
ACTIVE_FIELD_KEY = '"active_{value}":'

LOG_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the field a brain log line names the conversation under",
        why=(
            "seven modules attach the conversation a line is about and the recall trail is read "
            "beside the turn failures for the same chat, so a name that moved in one of them "
            "would split one investigation's evidence in two without any suite noticing, which "
            "is what happened for as long as the trail spelled it `session` (ADR-0009 "
            "one-vocabulary addendum); the memory runbook is the far side no import could reach, "
            "telling an operator to grep the field by name"
        ),
        sites=(Site(LOG_FIELDS, "SESSION_FIELD"),),
        mentions=(
            Mention(SUMMARIZING, FIELD_KEY),
            Mention(ENGINE, FIELD_KEY),
            Mention(TURN_OUTPUT, FIELD_KEY),
            Mention(TURN_CONTEXT, FIELD_KEY),
            Mention(RERANK_JUDGE, FIELD_KEY),
            Mention(CONVERSE_STREAM, FIELD_KEY),
            Mention(RECALL_AUDIT, FIELD_KEY),
            Mention(MEMORY_RUNBOOK, 'grep "{value}=<id>"'),
            Mention(MEMORY_RUNBOOK, "`{value}=None`"),
        ),
    ),
    Constant(
        label="the field a brain log line names the turn under",
        why=(
            "the turn is the id a failed turn's line, the tool calls that preceded it and every "
            "line about the handoff it asked for are joined by, which both runbooks state as a "
            "grep, so the seven modules that attach it and those instructions have to keep "
            "saying the same word (ADR-0009 one-vocabulary addendum); the swap path spelled it "
            "`turn` and `handoff` until the mint was read and a handoff id turned out to be the "
            "escalating turn's own"
        ),
        sites=(Site(LOG_FIELDS, "TURN_FIELD"),),
        mentions=(
            Mention(ENGINE, FIELD_KEY),
            Mention(TURN_CONTEXT, FIELD_KEY),
            Mention(CONVERSE_STREAM, FIELD_KEY),
            # The conductor's four are one set: its whole account of a handoff that never
            # started, each one a refusal an operator reaches for by turn, and this is the
            # module where the second spelling actually lived. A fifth refusal arriving under
            # another name is the drift, so the count is pinned.
            Mention(SWAP_CONDUCTOR, FIELD_KEY, occurrences=4),
            # The one line that names two turns, the refused one and the one the store is still
            # holding, tied to this same declaration through the qualified template.
            Mention(SWAP_CONDUCTOR, ACTIVE_FIELD_KEY),
            # The settler's three are one set for the same reason: the failure, the state that
            # could not be written and the record that could not be released are its whole
            # account of settling one handoff, and the swap runbook prints the first verbatim.
            Mention(SWAP_SETTLE, FIELD_KEY, occurrences=3),
            Mention(SWAP_RECOVERY, FIELD_KEY),
            Mention(BRAIN_PHASE, FIELD_KEY),
            Mention(TOOLS_RUNBOOK, "grep {value}=t-"),
            Mention(SWAP_RUNBOOK, "a handoff ended failed {value}=<turn id>"),
            Mention(SWAP_RUNBOOK, "`grep {value}=t-"),
        ),
    ),
    Constant(
        label="the field a brain log line names the delegated task under",
        why=(
            "one delegate's work is selected out of a batch by this field alone, the task id "
            "being minted inside the spawn tool and printed nowhere else, so the runner's line "
            "and the sentence telling a reader to select on it are the whole of what a reader "
            "has (ADR-0009 one-vocabulary addendum)"
        ),
        sites=(Site(LOG_FIELDS, "TASK_FIELD"),),
        mentions=(
            Mention(RUNNER, FIELD_KEY),
            Mention(TOOLS_RUNBOOK, "a subagent's `{value}` selects"),
        ),
    ),
    Constant(
        label="the field a brain log line names the fired schedule item under",
        why=(
            "one grep by item is meant to reach the fire, the work firing it caused and the "
            "ticker's own account of how it went, and it did not while the ticker spelled the "
            "same id `reminder_id` (ADR-0009 one-vocabulary addendum); the two runbooks print "
            "the field in the lines they tell an operator to look for"
        ),
        sites=(Site(LOG_FIELDS, "ITEM_FIELD"),),
        mentions=(
            # The ticker's three lines are one set: they are its whole account of one fire, and
            # the defect this entry closes was exactly that they moved as a set away from the
            # trail. A fourth arriving under another name is the drift, so the count is pinned.
            Mention(TICKER, FIELD_KEY, occurrences=3),
            # Both of the claim path's lines name the item, and the runbook prints one of them
            # verbatim, so losing either leaves an operator a corrupt record they cannot follow.
            Mention(SCHEDULE_CLAIMS, FIELD_KEY, occurrences=2),
            Mention(SCHEDULING_RUNBOOK, "grep {value}="),
            Mention(TOOLS_RUNBOOK, "`{value}` of the item that fired"),
        ),
    ),
    Constant(
        label="the field a brain log line names the call itself under",
        why=(
            "the fifth id is the one read as what the model asked for rather than as what the "
            "brain knows, and the tools runbook is where that reading is written down, so the "
            "name the sink prints and the name that warning is about cannot be allowed to drift "
            "apart (ADR-0009 one-vocabulary addendum)"
        ),
        sites=(Site(LOG_FIELDS, "CALL_FIELD"),),
        mentions=(
            Mention(TOOLS_RUNBOOK, "`{value}` is the fifth id"),
            Mention(TOOLS_RUNBOOK, "a `{value}=schedule-...`"),
        ),
    ),
)
