"""The couplings around the recall trail: the three words one of its lines is found by."""

from couplings import Constant, Mention, Site

RECALL_SINK = "brain/packages/memory/src/cortex_memory/audit.py"

TRAIL_READER = "scripts/trailwidth.py"

GATES_MODULE = "docs/modules/repo-gates.md"
LOCAL_DEV_RUNBOOK = "docs/runbooks/local-dev-wsl.md"
MEMORY_MODULE = "docs/modules/brain-memory.md"
MEMORY_RUNBOOK = "docs/runbooks/memory-pgvector.md"

FIELD_KEY = '"{value}":'

# How a sink writes the message a line is found by: the first argument of the call that emits it.
# The call and not the word alone, because this word is also the tail of the logger the sink writes
# through, so a bare needle would go on being found there after the message it names had moved.
TRAIL_CALL = '_logger.info("{value}"'

TRAIL_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the logger one recall-trail line is written through",
        why=(
            "this is the name an operator selects the trail by on a stream carrying every other "
            "line the brain writes, and three documents restate it while none of them can import "
            "it: the memory runbook says what turning the trail on produces, the local-dev "
            "runbook names it among the two per-line trails a deployment can raise or lower on "
            "its own, and the module contract states what the sink writes; a rename in the sink "
            "alone leaves all three instructing a reader about a logger nothing writes through "
            "(ADR-0038 named-logger addendum)"
        ),
        sites=(Site(RECALL_SINK, "_LOGGER_NAME"),),
        mentions=(
            Mention(MEMORY_RUNBOOK, "one `{value}` line per"),
            Mention(LOCAL_DEV_RUNBOOK, "the recall trail (`{value}`, behind"),
            Mention(MEMORY_MODULE, "`{value}` line per recall,"),
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
            Mention(RECALL_SINK, TRAIL_CALL),
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
            Mention(RECALL_SINK, FIELD_KEY),
            Mention(MEMORY_RUNBOOK, "`{value}` names every"),
            Mention(GATES_MODULE, "the recall trail's `{value}` field"),
        ),
    ),
)
