# Messages that are raised and logged still write their own numbers

**Status:** done 2026-09-10
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

Six sites build one string, log it, and raise it as a typed error's text, so the line an operator
sees has a value in the prose and again on the right:
`residency_moves._refuse_a_load_the_card_cannot_hold` twice, for a card that reports nothing and
for one that is short; `residency_watch` twice, for the daemon that could not be converged and for
the fresh sidecar whose worst stop the deadline no longer covers; `swap_builders`, for the deadline
pairing the composition root refuses to serve on; and `bounds.check_tool_call_deadline`, for the
call bound that outlasts the delegated run meant to contain it.

The two demands are opposed and both real. A log message needs to be constant so a `grep` matches
every instance of it and the varying parts sit in fields; an exception message needs to be
self-contained so the reply, the traceback and the runbook all say which numbers were refused.

The cheaper of the two fixes is gone. Dropping the log at each site and letting the catch print the
exception was traced: the four `SwapFailedError` sites share one catch that replies with a fixed
user-facing note and never reads the error's text, and `swap_builders` raises into a composition
root nothing guards. Dropping those logs would delete the numbers, or turn a designed boot refusal
into an interpreter traceback. So the remaining fix is two strings per site, a constant one for the
log call and the full one for the `raise`, which costs a second string that can diverge from the
first. `bounds.py` is the place to write the rule, being the only site whose fields are already
built by a function both lines call.

## History

- 2026-08-20: Filed by the close of [325](325-a-raised-message-is-also-a-logged-one.md), which
  traced its proposal and found it worked at one of the six sites. That one is closed (the
  supervisor's survived-SIGKILL failure is raised and no longer logged, both of its callers logging
  what they catch); these five are what was left.
- 2026-09-09: Reviewed, and the trigger had already fired. The count is six rather than five: the
  sixth site is `check_tool_call_deadline` in
  `brain/packages/orchestrator/src/cortex_orchestrator/bounds.py`, added 2026-08-21, one day after
  this entry was filed. It writes four numbers into its refusal message, logs that message, and
  attaches the same four as fields from `_pairing`. The five named above all still stand: two in
  `residency_moves.py`, two in `residency_watch.py` and one in `swap_builders.py`. No seventh
  exists: every site in the brain where a name is assigned, passed to a logging call and then
  raised is one of these six.
- 2026-09-10: Fixed as ADR-0051 decision 8, with the stated blocker reversed. The blocker was that
  the four `SwapFailedError` sites share a catch that never reads the error's text, so dropping a
  log there would delete the numbers. That stopped being true two days later:
  [R-350](350-a-failed-swap-in-says-nothing-brain-side.md) was committed 2026-08-22 and
  `swap_conductor._swap` now passes `str(err)` to `HandoffSettler.fail`, which writes the whole
  sentence to the handoff record and logs it as the `reason` field of a `WARNING` from
  `cortex_core.swap_settle`. The other two raise into `run_from_env` under `asyncio.run` with
  nothing guarding it, so the traceback has the sentence. At all six sites the self-contained text
  already reaches a reader by a channel other than the site's own log call, which is what makes a
  constant message there cost nothing. Each site now writes two strings. What keeps the pair
  together is a rule about the fields rather than a comparison of the two strings, which would have
  nothing to compare: every value the exception writes is attached to the log call as a field. Two
  field sets grew to satisfy it, the deadline refusals gaining the three terms of the worst stop
  through a new `ControlBounds.pairing_fields`, and `_pairing` gaining the sidecar count. Measured
  through the shipped formatter, the dispatch refusal's line went from 643 characters with four
  numbers twice to 215 with each once. Nine mutations over the four affected suites, one per
  message and one per field builder, each failed. What the close opened, that four of these lines
  attach their fields by a call `logfields.py` cannot read, is
  [R-619](619-four-refusal-lines-attach-their-fields-by-a-call.md).
