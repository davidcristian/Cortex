"""The couplings around the brain's two per-line trails: the words one of their lines is found by.

One of the data files `crosscheck.py` reads as a single registry, split off `logcouplings.py` when
the recall trail's logger brought that file to the 300-line cap, along the seam its docstring had
drawn from the day the first two of these landed. Five of the entries there are the name one work
identity rides under, wherever in the brain a line names it; the first five here are about a single
line on a single stream. The recall trail's three come first, ordered the way one of its lines
renders: the logger it is written through, the message it opens with, and the field whose width is
the subject of everything that reads it. The tool audit's logger and message follow, two words
rather than three: that trail has no reader outside the brain and no field of its own to measure,
and the identities its line carries are in `logcouplings.py` under the log vocabulary. The sixth
is a word of another kind, an identifier rather than anything a line prints, and the paragraph on
the derived
guard below says why it belongs beside these rather than in a part of its own.

A logger name needs this gate, and it has a declaration to be held to. The name is what
an operator selects this trail by on a stream carrying every other line the brain writes, and it is
restated by three documents that between them turn the trail on, name it among the loggers a
deployment can raise or lower, and state what the sink writes. A rename in the sink would leave all
three instructing a reader about a logger nothing writes through, with every gate green, which is
the same silence the two recall entries below were registered against. The sink names it in a
constant rather than inside the `getLogger` call so there is a declaration here at all; that was
the first of the two places in this registry where a far side gained a line to be tied by, the tool
audit's sink being the second, and both are argued at their ADRs rather than assumed here. That
is not this gate changing the code it reads: the name now sits where the rest of this brain's log
vocabulary already sits, `cortex_core.log_fields` declaring the field names for the same reason,
and `loggernames.py` learned that form in the same slice, so `samplecheck.py` goes on resolving a
documented sample of this trail against it.

**The tool audit's logger is the same shape one trail over, and two of its four restatements are a
different kind of claim.** Two are instructions, the tools runbook saying one such line is written
per dispatched call and the local-dev runbook naming it among the two per-line trails. The others
are `config_logging.py`'s docstring, which names this logger to argue that the shipped level is not
a knob since a deployment that turned INFO down would silently empty a record it is obliged to
keep, and that module's own suite, which proves the argument by writing a line under the name and
asserting the rendered result. Neither is an instruction, and both are registered anyway, because
what a rename does to them is identical: the argument would be about a logger nothing writes
through, and the proof would demonstrate it on a name the brain abandoned, in the module and the
suite a reader goes to when asking why the level is fixed. The registry is indifferent to the kind
of claim a far side makes, holding places that restate a value, and it already ties a docstring
restating a number and a live suite spelling an address for the same reason. The suite's two
spellings are two needles rather than one counted twice, the call it writes and the line it
asserts having different shapes and a rename having to move both.

The half this entry cannot hold is worth stating beside it: that same docstring sentence names
the recall trail in prose rather than by its logger, so it is tied to one of the two loggers it is
about, and nothing here would notice the other's rename in it, there being no name in the file to
notice.

Its message is held here rather than by the sample gate, which cannot reach this line at all.
`samplecheck.py` holds a documented log line to the call writing it, message included, but only
where a runbook prints a RENDERED line, and this one may not be printed: the sink builds its
`extra=` across statements and by condition, a success carrying a size where a failure carries an
error and four identities present only when the dispatch had them, so `logcalls.py` cannot read a
field list off it and any fenced sample of this trail fails as a call it cannot account for.
There is also no single field list to print. So the message is registered exactly like the logger
beside it, on the runbook sentence that tells a reader what to look for and on the two spellings in
the suite that proves the shipped level. The declaration is a second constant in the sink, the one
kind of far side this part has now added twice, and it is handed to the emitting call rather than
sat beside a literal of itself, so the module writes the word once.

Two entries share the suite's asserted line, and each renders its own half of it. That line
prints `LEVEL:logger:message` and so spends both values at once. The logger's needle used to spell
the message as fixed text, which made this data file a place restating a word it does not declare:
a rename of the message everywhere would have failed the logger's entry, sending a reader to the
wrong constant, and the fix would have been an edit to registry data rather than to the tree. Each
needle now renders its own value and anchors on the punctuation the format puts around it, the
logger on the colon that closes it and the message on the colon that opens it and the field that
follows.

The other two run the other way round, and the reader that declares them gates nothing.
`scripts/trailwidth.py` reads how wide the trail's widest field renders off captured container
logs, and to find a line at all it spells the sink's message and the key that field rides under. It
cannot import either: it is a standalone project that must never depend on the brain, which is the
same wall every entry in the log part is built over. So the declaration sits in the reader and the
sink holds the mentions, which the scan is indifferent to, comparing places and naming no master,
and which a reader of this file should still be told. That the reader gates nothing argues FOR
holding it, the same way `fixturecouplings.py` argues: a shipped value has a suite that runs on
every commit, while this one is read by hand, on a GPU, when somebody chooses to measure, and a
needle that stopped matching surfaces there as a stack with no trail lines rather than as a reader
looking for the wrong word.

The message's needle is the emitting call and never the word alone. A rendered line opens
`INFO:cortex.memory.recall:memory.recall `, the stdlib's own basic format being what the shipped
formatter builds on, so the word the reader looks for sits on every line twice: once as the
logger's tail and once as the message. A needle rendering the word alone would find the logger's
half in the sink too and hold nothing. The entry above is why that resemblance is now stated in one
place instead of being a coincidence two needles had to step around.

Three of these values are handed to their call as an identifier, and the place holding that is
registered rather than left implicit. `getLogger(_LOGGER_NAME)` and
`_logger.info(_MESSAGE, ...)` say nothing about the string they carry, so a sink binding one name
and passing a different literal is two names rather than one spelled twice, which is the shape the
rule against a word written twice, in `loggernames.py` for a logger and in `logcalls.py` for a
message, sees and lets through. The audit message is held at the call: its entry carries a mention
of the emitting call rendering the identifier, so a call handed another word, or the word written
out again, leaves that needle unfound, and the gate suite requires such a mention of every
registered binding a brain log call is handed (ADR-0009 held-call addendum). The same entry carries
a mention on the assertion the sink's own suite makes, which restates the value in the one place
that also proves the call wrote it (ADR-0009 declared-name addendum).

The sixth entry is what the two loggers carry instead, and it is one entry rather than one
apiece. That guard used to look each of these two names up by hand, so each logger was tied to
the spelling of its own lookup and a third self-named sink was held by nothing at all. It now reads
the self-named sinks out of the tree, a logger that is not its module's dotted path being one by
construction, and asks each of those modules for the name it binds its logger under. So there is no
logger name in the guard left to tie, and what is worth tying is the naming the derivation is read
by, which is one word for every sink there will ever be (ADR-0009 derived-sink addendum). It sits
in this part because the sinks it is about are the two this part is about, and because what it
guards is the same sentence the two logger entries above make: that the name the documents restate
is the name the brain writes through.

What is deliberately not here is the ADR that argued all three. Its pages quote whole rendered
lines as evidence of a run on a day, and this repo holds that a dated transcript is a record of the
past rather than a claim about today's code, which is the same line `samplecheck.py` draws when it
reads the runbooks and declares the decision records evidence.
"""

from couplings import Constant, Mention, Site

AUDIT_SINK = "brain/packages/tools/src/cortex_tools/audit.py"
RECALL_SINK = "brain/packages/memory/src/cortex_memory/audit.py"

AUDIT_SUITE = "brain/packages/tools/tests/test_audit.py"

CONFIG_LOGGING = "brain/packages/orchestrator/src/cortex_orchestrator/config_logging.py"
CONFIG_LOGGING_SUITE = "brain/packages/orchestrator/tests/test_config_logging.py"
TRAIL_READER = "scripts/trailwidth.py"
LOGGER_GUARD = "scripts/tests/test_loggernames.py"

GATES_MODULE = "docs/modules/repo-gates.md"
LOCAL_DEV_RUNBOOK = "docs/runbooks/local-dev-wsl.md"
MEMORY_MODULE = "docs/modules/brain-memory.md"
MEMORY_RUNBOOK = "docs/runbooks/memory-pgvector.md"
TOOLS_MODULE = "docs/modules/brain-tools.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"

# How the sink writes the field a line carries: a string key opening an ``extra=`` dict. The same
# shape the work identities are spelled in there, written out again rather than imported,
# because a part is data and the parts do not read each other: `registry.py` is the only thing that
# joins them, which is what lets an entry move house without the scan noticing.
FIELD_KEY = '"{value}":'

# How a sink writes the message a line is found by: the first argument of the call that emits it.
# The call and not the word alone, because this word is also the tail of the logger the sink writes
# through, so a bare needle would go on being found there after the message it names had moved.
TRAIL_CALL = '_logger.info("{value}"'

# How a sink writes the declaration the logger guard looks for: the assignment itself,
# which is where the identifier a `getLogger` call is handed is spelled the second time. The needle
# carries the quote that opens the value, so a module spending the same word in prose is not one of
# these places.
DECLARED_NAME = '{value} = "'

# How a module contract names that same identifier: in the sentence saying the sink declares its
# logger there rather than inside the call. Both contracts write it, each having to explain why its
# sink is spelled the way it is, and neither could reach the identifier by any import.
CONTRACT_NAME = "the module as `{value}`"

# How a sink's own suite spells the message its call really passed: the colon the stdlib's format
# puts in front of it and the quote closing the literal, the fields following on the line below.
# Its own half of that rendered line and never the logger's, for the reason the paragraph on the
# pair sharing one asserted line gives, and the closing quote is what keeps this off the forged
# line that suite feeds through a field, which spells the same words inside a longer string.
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
            "print as a rendered sample; the fourth place is the sink's own suite, which asserts "
            "the rendered line (ADR-0009 declared-name addendum), and the fifth is the emitting "
            "call, spending the binding by name, so a call handed another word fails here "
            "(ADR-0009 held-call addendum)"
        ),
        sites=(Site(AUDIT_SINK, "_MESSAGE"),),
        mentions=(
            Mention(TOOLS_RUNBOOK, "a bare `{value}` message followed by"),
            Mention(CONFIG_LOGGING_SUITE, '.info("{value}", extra='),
            Mention(CONFIG_LOGGING_SUITE, ':{value} tool=read"'),
            Mention(AUDIT_SUITE, ASSERTED_MESSAGE),
            Mention(AUDIT_SINK, "_logger.info({name},", name="_MESSAGE"),
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
            "it fails the guard as well as this entry, and what nothing else would notice is "
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
