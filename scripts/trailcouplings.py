"""The couplings around the brain's two per-line trails: the words one of their lines is found by.
"""

from couplings import Constant, Mention, Site

AUDIT_SINK = "brain/packages/tools/src/cortex_tools/audit.py"
RECALL_SINK = "brain/packages/memory/src/cortex_memory/audit.py"

AUDIT_SUITE = "brain/packages/tools/tests/test_audit.py"

CONFIG_LOGGING = "brain/packages/orchestrator/src/cortex_orchestrator/config_logging.py"
CONFIG_LOGGING_SUITE = "brain/packages/orchestrator/tests/test_config_logging.py"
TRAIL_READER = "scripts/trailwidth.py"
LOGGER_GUARD = "scripts/tests/test_logcalls.py"

GATES_MODULE = "docs/modules/repo-gates.md"
LOCAL_DEV_RUNBOOK = "docs/runbooks/local-dev-wsl.md"
MEMORY_MODULE = "docs/modules/brain-memory.md"
MEMORY_RUNBOOK = "docs/runbooks/memory-pgvector.md"
TOOLS_MODULE = "docs/modules/brain-tools.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"

FIELD_KEY = '"{value}":'

# How a sink writes the message a line is found by: the first argument of the call that emits it.
# The call and not the word alone, because this word is also the tail of the logger the sink writes
# through, so a bare needle would go on being found there after the message it names had moved.
TRAIL_CALL = '_logger.info("{value}"'

DECLARED_NAME = '{value} = "'

# How a module contract names that same identifier: in the sentence saying the sink declares its
# logger there rather than inside the call. Both contracts write it, each having to explain why its
# sink is spelled the way it is, and neither could reach the identifier by any import.
CONTRACT_NAME = "the module as `{value}`"

ASSERTED_MESSAGE = ':{value} "'

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
            "(ADR-0038 named-logger addendum); what holds this declaration to the call handed it "
            "is the guard the sixth entry below is about, which names no sink and so restates "
            "nothing here (ADR-0009 derived-sink addendum)"
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
    Constant(
        label="the logger one tool-audit line is written through",
        why=(
            "this is the name an operator selects the audit trail by on a stream carrying every "
            "other line the brain writes, and four places restate it while none of them can "
            "import it: the tools runbook says one such line is written per dispatched call, the "
            "local-dev runbook names it among the two per-line trails a deployment can raise or "
            "lower, the process entry's logging module names it to argue that the shipped level "
            "is not a knob, and that module's own suite writes a line under the name and asserts "
            "the rendered result to prove the argument; a rename in the sink alone leaves two "
            "runbooks telling an operator to select a trail nothing writes, one module arguing "
            "about the level of a logger that no longer exists, and one suite demonstrating the "
            "argument on a name the brain abandoned, all four green (ADR-0009 audit-logger "
            "addendum); what holds this declaration to the call handed it is the guard the sixth "
            "entry below is about, which names no sink and so restates nothing here (ADR-0009 "
            "derived-sink addendum)"
        ),
        sites=(Site(AUDIT_SINK, "_LOGGER_NAME"),),
        mentions=(
            Mention(TOOLS_RUNBOOK, "(one `{value}` line per call)"),
            Mention(LOCAL_DEV_RUNBOOK, "the tool audit (`{value}`, always on"),
            Mention(CONFIG_LOGGING, "audit trail (``{value}``,"),
            Mention(CONFIG_LOGGING_SUITE, 'getLogger("{value}").info'),
            Mention(CONFIG_LOGGING_SUITE, '== "INFO:{value}:'),
        ),
    ),
    Constant(
        label="the message one tool-audit line is found by",
        why=(
            "this is the word an operator looks for once the logger has selected the trail, and "
            "three places restate it while none of them can import it: the tools runbook says the "
            "line carries this and nothing else before its fields, and the process entry's own "
            "suite writes it under the trail's name and asserts the rendered result back to prove "
            "the shipped level; a rename in the sink alone leaves the runbook describing a "
            "message nothing writes and the suite passing on both its spellings at once, having "
            "renamed with itself (ADR-0009 audit-message addendum); the sample gate cannot stand "
            "in for this one, a line whose fields are built by condition being one no runbook may "
            "print as a rendered sample; the fourth place is the sink's own suite, which restates "
            "nothing and asserts the rendered line this sink emits, and so is the only thing "
            "holding this declaration to the call handed it, the guard next door reaching a "
            "logger name and no further (ADR-0009 declared-name addendum)"
        ),
        sites=(Site(AUDIT_SINK, "_MESSAGE"),),
        mentions=(
            Mention(TOOLS_RUNBOOK, "a bare `{value}` message followed by"),
            Mention(CONFIG_LOGGING_SUITE, '.info("{value}", extra='),
            Mention(CONFIG_LOGGING_SUITE, ':{value} tool=read"'),
            Mention(AUDIT_SUITE, ASSERTED_MESSAGE),
        ),
    ),
    Constant(
        label="the name a sink that named itself declares that name under",
        why=(
            "the guard holding these declarations to the calls handed them reads WHICH sinks are "
            "self-named out of the tree, a logger that is not its module's dotted path being one "
            "by construction, and then asks each of those modules for this one name, so the "
            "naming is what the derivation is read by and the guard, both sinks and any third "
            "have to keep spelling it alike (ADR-0009 derived-sink addendum); a sink that renames "
            "it reddens the guard as well as this entry, and what nothing else would notice is "
            "the guard itself going away, which takes the whole derivation with it and leaves the "
            "two declarations above tied to the documents restating them and to nothing at all "
            "saying the brain still writes through them; both module contracts name the "
            "identifier too, each explaining why its sink is spelled this way, and a rename that "
            "moved only the sinks would leave the pair of them pointing at a binding neither "
            "module makes"
        ),
        sites=(Site(LOGGER_GUARD, "DECLARATION"),),
        mentions=(
            Mention(AUDIT_SINK, DECLARED_NAME),
            Mention(RECALL_SINK, DECLARED_NAME),
            Mention(TOOLS_MODULE, CONTRACT_NAME),
            Mention(MEMORY_MODULE, CONTRACT_NAME),
        ),
    ),
)
