# ADR-0051: How a brain log line is rendered, and what it may contain

**Status:** Accepted (2026-09-19)

## Context

The brain configured logging with `logging.basicConfig(level=logging.INFO)` and nothing else, so the
shipped handler printed `levelname:name:message` and dropped every `extra=` field a call site
attached. Three modules had worked around that by writing their fields into their own messages (the
recall log, the tool audit, the rank fallback), and about thirty other lines repeated a model id, a
pid or a port in the message for the same reason. Once a formatter prints fields, each of those
workarounds prints a value twice.

A formatter that prints fields nobody listed is also the one place a careless `extra=` becomes a
leak, and AGENTS.md bans secrets in logs outright. An operator reads these lines through `docker
compose logs`, whose log driver ends a message at 16 KiB: a line past that arrives as several
entries, which `--tail` counts separately and `-t` stamps mid-value.

This record decides how a line is rendered, what a line may contain, and how its width is bounded
and checked. The field names for units of work are
[ADR-0046](ADR-0046-work-identities-on-log-lines.md); comparing a documented line with its call site
is [ADR-0045](ADR-0045-documented-log-lines.md).

## Decision

### The two renderings

1. **`cortex_core/log_format.py` has two renderings behind `build_formatter(style)`.** `plain`
   appends `key=value` pairs, in name order, after `logging.BASIC_FORMAT`, so the part before the
   fields is what `basicConfig` printed. `packed` writes one JSON object per line with the fields
   under their own `fields` key, so no field can shadow `level`, `logger` or `message`. `plain` is
   the default: the operator reads a terminal stream that uvicorn and llama.cpp also write into,
   which JSON would not make machine-readable, and `plain` keeps the runbooks' greps working.
   `CORTEX_LOG_FORMAT` selects it for the brain and `CORTEX_MODELHOST_LOG_FORMAT` for the model host
   sidecar; any other name raises `UnknownLogFormatError` at the entry point, before anything
   serves.
2. **The pair is one naming family**: how a record's fields are written down, laid out plainly or
   packed for transport. `plain`/`json` was rejected for naming one entry by wire format and the
   other by its absence; `loose`/`sealed` for making an operator guess what each prints.
3. **Only a process entry point configures logging.** `configure_logging` is the one core function
   that changes process-wide state, is called from `cortex_orchestrator.__main__` and the model
   host's `server.main`, and forces its handler on. `cortex_email` configures no logging and
   attaches no field, and so needs no dependency on the core. The two audit logs need a formatter to
   be installed, which is where handler configuration belongs.
4. **`RESERVED_ATTRS` is written out**, not derived from a sample record, and a test compares it
   with a real record in both directions, so a Python release that adds a `LogRecord` attribute
   fails a test rather than printing a standard-library field as though a caller had attached it.

### What a line contains

5. **The message is a constant sentence and every value on the line is a field.** A value the record
   holds is not interpolated into the message, so one `grep` on the sentence finds every instance of
   the line, and a runbook quotes the whole sentence and reads the value off the field beside it.
   The one exception is a word that is the sentence's own predicate: `residency_pass._unanswered`
   logs `a tier of the standing residency could not be %s`, where the word is `started` and is not a
   field.
6. **Ids, counts and reasons are fields; content never is.** Anything a person typed, a model
   generated or a tool returned stays off every line, because the secret defences below read names
   and URL syntax and cannot recognize conversation. The tool audit's `arguments` is the one
   attached value a model writes, recorded so the log says what was asked for, and it is bounded
   (decision 12).
7. **A line reporting a failure names what it failed on, when it accurately has one.** A pass guard
   (`ticker.run`, `residency_recheck.run`, the ticker's done-callback), a store that could not be
   read, and the gRPC pump's own failure have no subject and name none. A `try` that wrapped calls
   about two different models was split so each branch names its own: startup recovery clears the
   deep model (`the model host failed while clearing the deep model at boot`) and settles the cortex
   (`the model host was unreachable during boot recovery`) under two blocks, and the swap back takes
   the swapped-in model off the card
   (`the model host failed while taking the swapped-in model off the card`) apart from restoring the
   cortex. `restore_standing` returns `str | None`, `None` when the baseline residency is back and
   otherwise the id it failed on, so its retry and give-up lines add `model` (the cortex) and
   `failed_model` (the tier that failed), and `ResidencyRestoreError`'s text names both. The claim
   path's undecodable-record and quarantine lines add `item_id` and `dead_key`; the ticker's
   failures read their id off the claim beside them (the `gather` results zipped with the claims); a
   turn's failures add `session_id` and `turn_id`; an ignored client event adds `kind`.
8. **A message that is logged and raised is two strings.** The log call takes a constant message;
   the `raise` takes the self-contained sentence, which names the settings and writes out the
   numbers because it is read in a traceback and on a settled handoff record where no formatter
   runs. Every value the exception's text writes out is attached to the log call as a field, and
   where two lines describe one comparison the fields are built once
   (`ControlBounds.pairing_fields`, `_pairing` in `bounds.py`). This covers the six sites in
   `residency_moves`, `residency_watch`, `swap_builders` and `bounds`. The supervisor's
   survived-SIGKILL error is raised and not logged, since both its callers log what they catch; the
   control API's refusal line takes the level the status implies, `ERROR` for 5xx and `WARNING` for
   4xx.

### Secrets

9. **A field named for a secret prints `<redacted>`.** A name containing `token`, `password`,
   `passwd`, `secret`, `credential`, `apikey`, `api_key`, `authorization` or `cookie`,
   case-insensitively, is withheld (`log_secrets.py`), and the rule reaches inside a structured
   field ([ADR-0009](ADR-0009-tools-mcp.md)). It is a denylist, so a field nobody registered is
   printed rather than silently dropped, and a substring match, so `max_tokens` is withheld too: a
   token count costs less than a bearer token. The value is replaced and the key kept, so a withheld
   field reads differently from a missing one.
10. **A credential inside a URL is withheld by shape**, over the whole rendered line (message and
    traceback included) in both formatters, and per value before any cut (decision 13). The pattern
    ends on the `@` that closes a userinfo, so a bare email address and a credential-free URL are
    untouched. Shapes it cannot reach (a space or `/` in the userinfo, no scheme) are R-343.
11. **A DSN the database driver cannot parse is refused at startup.** A password `asyncpg` cannot
    read as an authority leaves a `ValueError` naming a fragment of it with no URL around it, which
    no URL rule can withhold. `MemoryConfig`'s validator (`dsn.py` reruns the driver's own parse
    steps) refuses such a DSN naming `CORTEX_MEMORY_DSN` and nothing it contains, and both
    `MemoryConfig` validators raise `MemoryConfigError`, not `ValueError`, because Pydantic renders
    a `ValueError` beside the validated input. The memory runbook has the command that re-checks the
    driver's steps after an upgrade.

### How wide a line can grow

12. **One rendered value uses at most `VALUE_CHARS`, 2,048 characters**, the 16 KiB driver message
    divided by eight, which leaves room for seven fields at that size on one line (eight exceed the
    16 KiB limit). It clears the widest value the tree attaches with room to spare: the recall log's
    `dropped` list cannot pass 1,581 characters at the shipped pool with 36-character ids, since no
    Python float renders in more than 24. The limit applies to the rendered text, after escaping, on
    both of `render_value`'s exits. A cut rendering is left unterminated and ends in
    `<cut N chars>`; a rendering the limit will cut is quoted rather than bare, so every cut ends
    mid-syntax and the marker, which contains whitespace, can never be read as a bare value's own
    text. Dropping whole elements with a count was rejected: `render_value` does not own the
    structure it renders, and a long string has no elements.
13. **A rendering is withheld before it is cut.** A cut between a URL's `://` and its `@` would
    remove the character the pattern anchors on and print the credential, so `_bound_value`
    withholds first, decides bare or quoted on the withheld rendering (which can be longer), then
    cuts. The whole-line pass stays for the message and traceback; running it twice changes nothing.
    A secret-named field is replaced before rendering, so no cut can reach inside it.
14. **The packed rendering keeps its values whole.** A limit inside it would corrupt the object or
    misstate its shape; it shares the credential passes and not the limit (R-336).
15. **The widest line each shipped sink builds is checked.**
    `orchestrator/tests/test_widest_line.py` drives each sink with every field whose text the brain
    does not choose set past `VALUE_CHARS`, and asserts the line stays under 16,383 characters,
    which fields were cut and which keys it has. The sinks are read from the composition root: every
    name ending in `Sink` that a `cortex_orchestrator` module imports from `cortex_tools` or
    `cortex_memory`, which must equal the sinks a test drives plus the exempted ones
    (`TeeAuditSink`, which logs nothing itself); a stale exemption fails. The tool audit is the
    widest, with five wide fields (`tool`, `call_id`, `arguments`, `error`, and a `session_id` whose
    length nothing checks between the wire and the line). The recall-log test records through a
    `MemoryRecaller` built as the composition root builds it, so the ids are the shipped factory's;
    the `dropped` field passes the limit at a 60-character id, and the id is not bounded at the
    port, being the store's identity.

### Reading a live recall log's width

16. **A width is read off a live stack by a recipe and a test-covered reader.**
    `orchestrator/tests/recall_trail_probe.py` runs inside the brain container, through the shipped
    composition root, sink and formatter, seeding each pass with the 41-note corpus and asking 75
    distinct queries; `just recall-width` runs the docker commands; `scripts/trailwidth.py` reads
    the captures and reports the `dropped` field and the whole line per cohort of dropped
    candidates. The width is measured from where `BASIC_FORMAT` begins, so a compose prefix is not
    counted, and a line qualifies by the message where the formatter puts it. No `-t` capture is
    taken, since its stamps fall mid-line and inflate the width, and the reader never writes out the
    16 KiB limit. It measures the `plain` rendering only, because `VALUE_CHARS` applies there, and
    its refusal names a `packed` line when the capture holds one. The measurement is recorded with
    its date rather than checked, since no code compares anything against it; the reader's search
    texts are registry entries (`scripts/trailcouplings.py`,
    [ADR-0042](ADR-0042-cross-tree-constant-registry.md)).

## Consequences

- One grep on a sentence finds every instance of a line, and a runbook quotes a constant sentence.
- A line stays one driver entry, so `--tail` and `-t` stay usable. The widest sink uses five of the
  seven fields the limit leaves room for, and the check fails on the day a line passes 16 KiB.
- A deployment that wants a whole value reads the store the line's id points at, not the log.
- A crashed entry point's traceback still reaches stderr without the formatter (R-664); a packed
  line is unbounded (R-336); the line ceiling rests on the least sampled cohort (R-471).
- Readings: [log line widths](../readings/log-line-widths.md).

## Alternatives rejected

- **JSON as the default rendering:** unreadable at a glance, on a stream that is not all JSON.
- **An allowlist of printable fields:** a field nobody registered would vanish without a word.
- **Dropping the log call where a message is also raised:** the sentence does reach a reader at all
  six sites (the swap settle records it, the two startup refusals print a traceback), but never as a
  line with a constant message and the numbers as fields.
- **A marker with no whitespace:** would let a bare value contain the marker.
- **Logging the entry point's fatal error, or documenting percent-encoding, instead of the DSN
  check:** neither withholds a credential fragment with no URL around it (the first is still R-664).
- **Checking the measured width:** it is a dated measurement nothing compares against.

## Related

- [brain-core module contract](../modules/brain-core.md) (`log_fields`, `log_format`),
  [brain-orchestrator](../modules/brain-orchestrator.md),
  [brain-model-manager](../modules/brain-model-manager.md),
  [repo checks](../modules/repo-checks.md) (`trailwidth.py`).
- Runbooks: [local-dev-wsl](../runbooks/local-dev-wsl.md),
  [memory-pgvector](../runbooks/memory-pgvector.md), [model-swap](../runbooks/model-swap.md),
  [scheduling](../runbooks/scheduling.md).
- [ADR-0038](ADR-0038-ranked-recall.md) (the recall log), [ADR-0009](ADR-0009-tools-mcp.md) (the
  tool audit), [ADR-0045](ADR-0045-documented-log-lines.md),
  [ADR-0046](ADR-0046-work-identities-on-log-lines.md).
- Open: [R-336](../refinements/tasks/336-packed-values-keep-their-whole-length.md),
  [R-343](../refinements/tasks/343-a-userinfo-the-pattern-cannot-reach.md),
  [R-471](../refinements/tasks/471-the-lines-ceiling-is-the-least-sampled-cohort.md),
  [R-664](../refinements/tasks/664-a-startup-traceback-reaches-stderr-with-no-formatter.md).
