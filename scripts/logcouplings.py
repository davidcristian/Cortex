"""The couplings around the brain's log field names: the name one work identity is written under."""

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

FIELD_KEY = '"{value}":'

ACTIVE_FIELD_KEY = '"active_{value}":'

LOG_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the field a brain log line names the conversation under",
        why=(
            "eleven modules attach the conversation a line is about and the recall trail is read "
            "beside the turn failures and the handoff for the same chat, so a name that moved in "
            "one of them would split one investigation's evidence in two without any suite "
            "noticing, which is what happened for as long as the trail wrote it `session` "
            "(ADR-0046 decision 1); the two runbooks are the far side no import "
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
            Mention(BRAIN_PHASE, FIELD_KEY, occurrences=3),
            Mention(MEMORY_RUNBOOK, 'grep "{value}=<id>"'),
            Mention(MEMORY_RUNBOOK, "`{value}=None`"),
            Mention(SWAP_RUNBOOK, 'failed reason="<what happened>" {value}=<chat id>'),
            Mention(SWAP_RUNBOOK, "`grep {value}=`"),
        ),
    ),
    Constant(
        label="the field a brain log line names the turn under",
        why=(
            "the turn is the id a failed turn's line, the tool calls that preceded it, the "
            "recall it made and every line about the handoff it asked for are joined by, which "
            "three runbooks state as a grep, so the nine modules that attach it and those "
            "instructions have to keep "
            "saying the same word (ADR-0046 decision 1); the swap path wrote it "
            "`turn` and `handoff` until the mint was read and a handoff id turned out to be the "
            "escalating turn's own"
        ),
        sites=(Site(LOG_FIELDS, "TURN_FIELD"),),
        mentions=(
            Mention(ENGINE, FIELD_KEY),
            Mention(TURN_CONTEXT, FIELD_KEY),
            Mention(CONVERSE_STREAM, FIELD_KEY),
            Mention(SWAP_CONDUCTOR, FIELD_KEY, occurrences=4),
            Mention(SWAP_CONDUCTOR, ACTIVE_FIELD_KEY),
            Mention(SWAP_SETTLE, FIELD_KEY, occurrences=3),
            Mention(SWAP_RECOVERY, FIELD_KEY),
            Mention(BRAIN_PHASE, FIELD_KEY),
            Mention(RERANK_JUDGE, FIELD_KEY),
            Mention(RECALL_AUDIT, FIELD_KEY),
            Mention(MEMORY_RUNBOOK, 'grep "{value}=<id>"'),
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
            "has (ADR-0046 decision 1)"
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
            "ticker's own account of how it went, and it did not while the ticker wrote the "
            "same id `reminder_id` (ADR-0046 decision 1); the two runbooks print "
            "the field in the lines they tell an operator to look for"
        ),
        sites=(Site(LOG_FIELDS, "ITEM_FIELD"),),
        mentions=(
            Mention(TICKER, FIELD_KEY, occurrences=3),
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
            "apart (ADR-0046 decision 1)"
        ),
        sites=(Site(LOG_FIELDS, "CALL_FIELD"),),
        mentions=(
            Mention(TOOLS_RUNBOOK, "`{value}` is the fifth id"),
            Mention(TOOLS_RUNBOOK, "a `{value}=schedule-...`"),
        ),
    ),
)
