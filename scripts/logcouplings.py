"""The couplings around the brain's own log vocabulary: the words one of its lines is found by."""

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

TRAIL_READER = "scripts/trailwidth.py"

GATES_MODULE = "docs/modules/repo-gates.md"
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

# How a sink writes the message a line is found by: the first argument of the call that emits it.
# The call and not the word alone, because this word is also the tail of the logger the sink writes
# through, so a bare needle would go on being found there after the message it names had moved.
TRAIL_CALL = '_logger.info("{value}"'

LOG_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the field a brain log line names the conversation under",
        why=(
            "eleven modules attach the conversation a line is about and the recall trail is read "
            "beside the turn failures and the handoff for the same chat, so a name that moved in "
            "one of them would split one investigation's evidence in two without any suite "
            "noticing, which is what happened for as long as the trail spelled it `session` "
            "(ADR-0009 one-vocabulary addendum); the two runbooks are the far side no import "
            "could reach, telling an operator to grep the field by name"
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
            Mention(SWAP_CONDUCTOR, FIELD_KEY, occurrences=4),
            Mention(SWAP_SETTLE, FIELD_KEY, occurrences=3),
            Mention(SWAP_RECOVERY, FIELD_KEY),
            # The deep phase's two cadence spellings, the reading and the no-reading arms. Pinned
            # at two because they are the only lines a handoff that WORKED ever writes, so losing
            # either leaves a chat that escalated successfully with no evidence it ever did.
            Mention(BRAIN_PHASE, FIELD_KEY, occurrences=2),
            Mention(MEMORY_RUNBOOK, 'grep "{value}=<id>"'),
            Mention(MEMORY_RUNBOOK, "`{value}=None`"),
            Mention(SWAP_RUNBOOK, 'failed reason="<what happened>" {value}=<chat id>'),
            Mention(SWAP_RUNBOOK, "`grep {value}=`"),
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
            Mention(TOOLS_RUNBOOK, "`grep {value}=` on one id gathers"),
            Mention(SWAP_RUNBOOK, "{value}=<turn id>"),
            Mention(SWAP_RUNBOOK, "`grep {value}=` on that id"),
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
    Constant(
        label="the message one recall-trail line is found by",
        why=(
            "the reader that measures this trail selects a line out of a capture by this message "
            "and spells it itself, having no way to import it, so a rename in the sink leaves a "
            "hand run measurement refusing every capture in the words of a stack that wrote no "
            "trail (ADR-0038 tied-needle addendum); the runbook says the line carries this word "
            "as its message and tells an operator to grep for it, and one of those two sentences "
            "is what a rename makes false while the other still works by accident, the logger's "
            "own name ending in the same word"
        ),
        sites=(Site(TRAIL_READER, "TRAIL_MESSAGE"),),
        mentions=(
            Mention(RECALL_AUDIT, TRAIL_CALL),
            Mention(MEMORY_RUNBOOK, "`{value}` message"),
            Mention(MEMORY_RUNBOOK, "grep {value}"),
        ),
    ),
    Constant(
        label="the field a recall-trail line names the candidates it dropped under",
        why=(
            "this field's rendered width is what `VALUE_CHARS` is argued generous against, and "
            "the reader that measures it cuts the value out of a captured line by this name, so "
            "a rename in the sink alone leaves the one measurement behind that argument reading "
            "nothing at all (ADR-0038 tied-needle addendum); the runbook names the field to say "
            "which question it answers and the module contract to say what is being measured, "
            "and neither could be reached by any import"
        ),
        sites=(Site(TRAIL_READER, "TRAIL_FIELD"),),
        mentions=(
            Mention(RECALL_AUDIT, FIELD_KEY),
            Mention(MEMORY_RUNBOOK, "`{value}` names every"),
            Mention(GATES_MODULE, "the recall trail's `{value}` field"),
        ),
    ),
)
