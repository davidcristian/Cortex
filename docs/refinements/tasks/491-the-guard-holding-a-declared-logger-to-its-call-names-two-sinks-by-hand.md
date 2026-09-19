# The test comparing a declared logger with its call names two sinks by hand

**Status:** done 2026-08-30
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

What compares a sink's `_LOGGER_NAME` with the name its `getLogger` call really receives is
`test_the_committed_brain_declares_both_spellings_a_logger_is_claimed_in` in
`scripts/tests/test_logcalls.py`. It asserts that `logcalls.loggers` maps `cortex.tools.audit` to
`cortex_tools/audit.py` and `cortex.memory.recall` to `cortex_memory/audit.py`, and that reader
answers with the name the call passes, so a sink binding one name and passing another fails those
lookups.

Both names are written out by hand. A third self-named sink is covered by nothing until somebody
remembers to add a line, which is the shape [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)'s
derived set is against, and which `flagcheck.py` already solves for another rule. The set here is
derivable the same way: `logcalls.loggers` already returns every logger the brain declares against
the file declaring it, and a self-named sink is a module whose top level binds a string that its own
`getLogger` call is handed.

## History

- 2026-08-29: opened by the close of
  [R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md), whose mutation table
  measures the test catching both sinks and says nothing about a third.
- 2026-08-30: closed as [ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 13. The
  premise held in both of its shapes when checked again: a third self-named sink written into the
  committed brain, binding a name and passing another literal, left the check suite,
  `check-crosscheck` and `check-samplecheck` all green, and so did the same probe binding its name
  under another identifier. The test now reads the self-named sinks off the tree, a logger that is
  not its module's dotted path being one, and requires that set to equal the names brain modules
  bind under `_LOGGER_NAME`. Comparing two readings as sets covers a call passing another name, a
  declaration the call stopped passing, a sink naming itself with a bare literal, and a sink binding
  its name under some other identifier. The first thing this entry asked to weigh was decided
  against the reader: `logcalls.py` reads any tree and its one rule is about an ambiguity in the
  reading, where this is a claim about the committed brain, and a reader failing on a bare literal
  would impose a rule over every fixture it walks. The 300-line cap did not decide it. The second
  was answered by what the documents were compared with all along: `_LOGGER_NAME` in each sink,
  which has not moved, so the derived test costs the registry nothing. What the two literals gave it
  was a far side making the test undeletable, and that is restored as one registry entry on the
  identifier the derivation reads, used by both sinks, both module contracts and the test itself.
  Opened by this close:
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), the same
  question one word over.
