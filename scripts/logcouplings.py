"""The couplings around the brain's own log vocabulary: the name one work identity rides under.

One of the data files `crosscheck.py` reads as a single registry. Its subject is a name a log line
is written with rather than a value one carries: five identities, one entry each. The recall
trail's own three words are in `trailcouplings.py`, which split off when the logger brought this
file to the 300-line cap.

`cortex_core.log_fields` declares all five, and only the tool audit spends them as code; every
other line writes one inside its own `extra=`, where the literal is what an operator greps for, and
the runbooks name the fields to grep. Those far sides are tied here rather than made to import.

Two identities were once written two ways at once and neither split was visible to any suite, which
is what these entries report. The ADR-0009 one-vocabulary and named-conversation addenda record
both splits, why the Redis codecs and `NotifyRequest.reminder_id` are deliberately not tied to
these names, and why the swap path's `handoff` field is an escalating turn's id.
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
            # The swap path's four modules, which carry the conversation as of the
            # named-conversation addendum. The two counts are pinned for the same reason the turn
            # entry pins them: the conductor's four refusals are its whole account of a handoff
            # that never started, and the settler's three are its whole account of settling one,
            # so a fifth or a fourth arriving without the conversation is the drift.
            Mention(SWAP_CONDUCTOR, FIELD_KEY, occurrences=4),
            Mention(SWAP_SETTLE, FIELD_KEY, occurrences=3),
            Mention(SWAP_RECOVERY, FIELD_KEY),
            # The deep phase's two cadence spellings, the reading and the no-reading arms. Pinned
            # at two because they are the only lines a handoff that WORKED ever writes, so losing
            # either leaves a chat that escalated successfully with no evidence it ever did.
            Mention(BRAIN_PHASE, FIELD_KEY, occurrences=2),
            Mention(MEMORY_RUNBOOK, 'grep "{value}=<id>"'),
            Mention(MEMORY_RUNBOOK, "`{value}=None`"),
            # The verbatim failed-settle sample, anchored on the end of the message and on the
            # field that sorts in front of this one. That anchor is what pins the ORDER of the
            # three fields, which nothing did while the sample printed an order the formatter
            # never renders: the message is fixed, `reason` sorts first, this one sorts second,
            # and the turn entry's needle below holds the third (ADR-0009 bare-id addendum).
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
            # Both greps carry the sentence around the field rather than the field alone, which
            # is what stops the `t-` prefix coming back: each told an operator to search for a
            # shape no id has ever worn, and this needle held the fiction in place until the
            # bare-id addendum corrected both sentences.
            Mention(TOOLS_RUNBOOK, "`grep {value}=` on one id gathers"),
            # The failed-settle line the swap runbook prints verbatim. The needle is the field
            # rather than the message plus the field, because the fields are printed in NAME
            # order by the formatter and the message no longer touches this one: the conversation
            # sorts between them (`reason`, `session_id`, `turn_id`). The conversation entry's
            # needle above carries that message, so the order is pinned there for both of us.
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
)
