# ADR-0045: Documented log lines are compared with the code that writes them

**Status:** Accepted (2026-09-15)

## Context

Runbooks print rendered brain log lines to tell an operator what to expect on a stream while
somebody is waiting: the failed handoff settle, the spill watch, the gRPC server's boot line, the
tool audit's line. A runbook is text and a line's fields are a dict in a module elsewhere, so a
field a call stopped or started attaching, a level that changed or a renamed logger left the sample
printing a line the code never emits, with every check green. The constant registry
([ADR-0042](ADR-0042-cross-tree-constant-registry.md)) compares a value written in several places,
but a field list is a set of keys and reduces to no value search text could match.

Two audit records, the tool audit ([ADR-0009](ADR-0009-tools-mcp.md)) and the recall record
([ADR-0038](ADR-0038-ranked-recall.md)), name their own logger rather than using their module path,
because their lines are read as a series. Their logger name and message are restated in runbooks,
module contracts and a neighbouring suite, which could go out of date the same way.

The rendering these samples are compared against is the shipped `PlainFormatter`:
`LEVEL:logger:message` followed by `name=value` fields sorted by name.

## Decision

### The check

1. **A scan of its own, `scripts/samplecheck.py`, run by `just check`.** For every sample it finds,
   four things must agree with the call that writes the line: the level, the logger (resolved to
   the module that owns it), the message, and the field names as a sequence. Printed order is name
   order and so follows from the key set, which makes one sequence comparison cover membership and
   order together. It is not folded into `crosscheck.py`, because a field list is not a value.
2. **Field names, never field values.** A sample's values are often placeholders
   (`<chat id>`, `<what happened>`), and a captured value is a dated reading the constant registry
   already declines to compare. Checking values here would contradict that decision from a second
   place.
3. **Runbooks only.** A runbook is written in the present tense and opened while something is
   broken, so it is a contract; the walk reads `docs/runbooks/` and nothing else.
4. **Samples are found, not registered.** Every fenced line shaped like a rendered one is a sample,
   so a sample written tomorrow is checked tomorrow, and a runbook quoting a line no module writes
   fails rather than being skipped. A sample is a line inside a fence and never a sentence, so prose
   naming a line is not checked. The line is found by its `LEVEL:logger:` prefix, whatever
   decoration (a compose prefix, a `#`) stands in front of it, and the message ends at the first
   `name=` that opens outside a quoted value (`logsamples.py`).

### Reading the brain without importing it

5. **The source is parsed with `ast`, never imported.** An `extra=` dict spans several lines, and a
   brace counter that followed it would be a partial Python parser. `ast` executes nothing, so
   `scripts/` still does not import the brain. A call whose level is chosen at run time,
   `logger.log(level, ...)`, is reported by name as unreadable rather than as a message nothing
   logs.
6. **Which module owns a logger** (`loggernames.py`): `getLogger(__name__)` is the module's dotted
   path, a string literal is read directly, and a bare identifier is resolved against the module's
   own top level (`moduleconstants.py`). An imported name is not followed, and a name claimed by two
   files is a fault.
7. **What one call writes** (`logcalls.py`): the message is a literal or a bare identifier resolved
   against the module's own top level; one assembled at the call cannot be quoted.
8. **One name and one message, written once.** A literal logger name or log message that the same
   module also binds at its top level is refused, naming every binding. The constant registry
   compares documents with the binding, so a second copy could move alone and leave them restating
   a word the brain no longer writes. The rule runs over log calls, not over names, so a module
   binding a string for another purpose is never covered.
9. **Field lists are read in three forms under four conditions** (`logfields.py`): a mapping written
   out at the call, a bare name, and that name combined with a mapping written out at the call. A
   name is followed only (a) inside the innermost function holding the call, (b) to one binding at
   the top level of that function's body above the call, (c) to a mapping written out with plain
   string keys, and (d) when nothing else in the function names it except as the `extra=` of a log
   call. Under those conditions the mapping reaching the call is the one written out. Anything else
   is refused with the line and the reason; a `**` spread is refused with a fault naming
   `extra | {...}` as the union that is read. Which calls are log calls is handed in by
   `logcalls.py`, so the level table exists once.
10. **A call is not rewritten to become quotable.** The check compares a document with the code;
    bending a call to suit the reader would invert that.

### A line whose fields the source cannot list

11. **It is compared with the whole lines its own package suite asserts** (`assertedlines.py`). Two
    forms have no field list in the source: a mapping grown by condition after it is bound, which is
    how the tool audit writes its line, and a mapping another call returns, which is how the two
    bound pairings in `cortex_orchestrator/bounds.py` write theirs. `logcalls.logged` raises
    `UnreadFieldsError` for them, reporting the level it read; `samplecheck.py` compares that level,
    then passes the sample when a line the suite asserts whole prints the same logger, message and
    fields in the same order. The chain has two links: the sample equals a suite assertion, which
    this check compares, and the assertion equals the formatter's output, which pytest asserts. The
    reader follows no branch; which condition a line stands for is said by the test that asserts it.
12. **Four restrictions keep that reading a proof.** Only a string on one side of `assert x == "..."`
    is read, since a containment check says a line contains that much and not that it is the line.
    It is anchored at its start and holds no newline. And only the `tests` directory beside the
    call's own `src` is read: the orchestrator's logging suite asserts a one-field
    `cortex.tools.audit` line to prove the shipped level, which the sink never prints. A package
    with no suite, or a suite file that is not text or does not parse, fails the check.

### The self-named audit records

13. **A self-named sink declares its logger name and passes it.** `_LOGGER_NAME` is bound in
    `cortex_tools/audit.py` and in the recall sink and handed to `getLogger`, which gives the
    constant registry a declaration to compare the runbooks, the process entry's docstring and its
    suite against (`scripts/trailcouplings.py`). A guard in `scripts/tests/test_loggernames.py`
    compares two readings of the brain as sets: the loggers that are not their module's own path,
    and the modules binding `_LOGGER_NAME`. Equality catches a call passing another name, a
    declaration the call stopped passing, a sink naming itself with a bare literal and a name bound
    under another identifier. The identifier `_LOGGER_NAME` is itself a registry entry, used by both
    sinks and both module contracts.
14. **The tool audit declares its message too, and its call is compared with it.** The audit line's
    fields vary by condition, so before decision 11 no sample could reach it; `_MESSAGE` is bound
    beside `_LOGGER_NAME`, passed to `_logger.info`, and compared with the tools runbook and the
    level suite. The emitting call is itself a mention of the entry, `_logger.info({name},` with
    `name="_MESSAGE"`, and a site is credited with the name it declares. A guard in
    `scripts/tests/test_crosscheck.py` requires, of every registry site a brain log call is handed
    as its message (`logcalls.handed`), a mention on the handing line; for a call the formatter
    wraps, the fault names the shorter template `{name},`. Search text is matched as written, so
    text that folds whitespace was declined. Each piece of search text is anchored on the format's
    own punctuation, and registry data never writes out a value another entry declares.
15. **No further rule for a binding and a different word in its call.** That state already fails:
    the logger-name guard and each sink's own package suite, which asserts whole rendered lines.
    Those two are registry mentions, so deleting one fails the scan. A convention that a package
    suite imports its message constant and asserts `getMessage()` against it is stated and not
    enforced.

## Consequences

- A field a call starts or stops attaching, a level change and a renamed logger or message each
  fail `just check` on the day they happen, wherever a runbook prints that line.
- The tool audit's line can be printed only through its suite's assertions; the tools runbook
  prints one sample per case, and which condition each stands for is prose.
- `scripts/` reads call sites as well as declarations, still without importing the brain.
- A runbook sample that quotes a line through an f-string or a helper assertion is not proven and
  fails, naming the runbook.
- Which lines a runbook should print at all is outside this check: it compares what is printed with
  what is written, and says nothing about coverage.

## Alternatives rejected

- **Re-rendering samples through the real formatter:** needs the brain importable from `scripts/`
  and would have to be taught what each placeholder stands for.
- **Registering samples by hand:** leaves each new one unchecked until someone remembers it.
- **Following the `if` that sets a field:** a guessed branch compares a document with a line nothing
  prints.
- **A registry field marking a value as a log message, or a naming convention for messages:** the
  brain binds many `*_MSG` strings that are model-facing refusals, not log messages.

## Related

- The [repo checks module contract](../modules/repo-gates.md),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md) (the registry the sink names are compared
  through), [ADR-0046](ADR-0046-work-identities-on-log-lines.md) (the field names these lines
  include), [ADR-0009](ADR-0009-tools-mcp.md) (the tool audit),
  [ADR-0038](ADR-0038-ranked-recall.md) (the recall record),
  [ADR-0051](ADR-0051-log-line-rendering.md) (the rendered field order).
- Runbooks this check reads today include [tools-mcp](../runbooks/tools-mcp.md) and
  [model-swap](../runbooks/model-swap.md).
