# A declared message and a different word in the call

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-30 by the close of
[R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), which
taught the reader the spelling that entry asked for and left the half its own title named.

`brain/packages/tools/src/cortex_tools/audit.py` binds `_MESSAGE = "tool.invocation"` and hands it
to `_logger.info`. The constant registry ties the tools runbook and the process entry's logging
suite to that binding, so a call passing some **other** literal leaves three documents restating a
word the brain does not write. That is two words rather than one spelled twice, which is the shape
the rule against a doubled spelling sees and lets through, for a message exactly as for a logger
name. What refuses it is `brain/packages/tools/tests/test_audit.py`, which asserts four whole
rendered lines, and the registry names that assertion so it cannot be deleted in silence (ADR-0009
declared-name addendum). One package's own suite, named by hand.

**Why the logger's derivation does not transfer, measured rather than assumed.** That guard reads a
structural set off the calls, a logger that is not its module's dotted path being a self-named sink
by construction, and holds it equal to the names brain modules bind under `_LOGGER_NAME`. A message
has no such naming to be held to. The brain binds about twenty top-level strings whose names say
`MESSAGE` or `MSG` and only five are log messages; the rest are model-facing refusals
(`BUDGET_EXHAUSTED_MSG`, `DENIED_MSG`, `TAINTED_TASK_MSG` and a dozen more in
`brain/packages/core/src/cortex_core/`). A convention introduced here would sit one letter from
that family and redden every one of them (ADR-0009 handed-message addendum).

**Two paths worth weighing, both real.**

The cheaper one uses the registry's own vocabulary. A `Mention` may render `{name}` as well as
`{value}`, which is how the overlay's `var(--roll)` is held beside the declaration paying it, so
the audit message's entry could carry a mention of the emitting call rendering the identifier,
`_logger.info({name},` at the sink. Then a call passing another word, or writing the declared word
out again, leaves the needle unfound and `check-crosscheck` fails. It costs one relaxation:
`crosscheck.spend_fault` refuses a name spent where no MENTION renders the value under it, and here
the value is paid by the entry's own `Site`, so either a companion mention duplicates the site's
reading or the rule learns that a site pays the name it declares. The hole that leaves is an entry
whose author forgets the call mention, which a derived guard could close: every registry site
naming a brain module and an identifier that module's log calls are handed must carry such a
mention.

The other path gives the registry a way to say which of its values is a log message, held by an
equality rather than trusted: the sites in brain modules whose identifier a log call is handed, set
against the entries marked as messages, so a marker forgotten and a marker on the wrong entry are
each a red. That is a change to `couplings.py`, which is today entirely read by `crosscheck.py`,
and a field no scan reads would be new in this tree.

**What is already true and should not be rebuilt.** Two of the four declared messages outside this
sink are held about as firmly as anything here: `cortex_orchestrator/abandon.py` and
`cortex_core/brain_phase.py` have suites that import the constant and assert the emitted record
against it, so a call passing another word is a red in the package that owns it. Neither is
arranged by a gate and neither is written down anywhere, which is worth stating in whatever closes
this: a convention nobody named is doing most of the work.

## Trail

- 2026-08-30: opened by the close of
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), whose
  mutation table measures the doubled spelling going from green to three reds and says nothing
  about a call carrying a different word.
