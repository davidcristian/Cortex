# Messages that are raised and logged still spell their own numbers

**Status:** landed 2026-09-10
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Six sites build one string, log it, and raise it as a typed error's text, so the line an operator
sees carries a value in the prose and again on the right:
`residency_moves._refuse_a_load_the_card_cannot_hold` twice, for a card that reports nothing and
for one that is short; `residency_watch` twice, for the daemon that could not be converged and for
the fresh sidecar whose worst stop the deadline no longer clears; `swap_builders`, for the
deadline pairing the composition root refuses to serve on; and `bounds.check_tool_call_deadline`,
for the call bound that outlasts the delegated run meant to contain it.

The two demands are genuinely opposed and both are real. A log message needs to be constant so a
`grep` matches every instance of it and the varying parts sit in fields; an exception message needs
to be self-contained so the reply, the traceback and the runbook all say which numbers refused.
Nothing here is wrong; it is one value read twice on one line, on lines that fire rarely and are
read closely.

What is different from when this was first written is that the cheaper of the two shapes is gone.
The alternative worth weighing first was to drop the *log* at each site and let the catch print the
exception, and that was traced: the four `SwapFailedError` sites share one catch that answers a
fixed user-facing note and never reads the error's text, and `swap_builders` raises into a
composition root nothing guards at all. Dropping those logs would not move the numbers, it would
delete them, or turn a designed boot refusal into an interpreter traceback. So the only shape left
is two strings per site, a constant one for the log call and the full one for the `raise`, which
costs a second string that can drift from the first.

This was filed waiting for a sixth site, on the reasoning that a sixth site is worth a rule. The
sixth arrived the day after it was filed and nobody read it as the arrival:
`check_tool_call_deadline` spells four numbers in its refusal message, logs that message, and
attaches the same four as fields from `_pairing`, whose docstring says it exists so both lines
carry the same set. Its own comment
states the duplication in this entry's terms, that the message is the one place the numbers stay in
the prose because it is read where no formatter runs. So the count that decides this is six, and
what remains is to choose the rule: two strings per site, a constant one for the log call and the
full one for the `raise`, and something that holds the pair together. `bounds.py` is the site to
write it against, being the only one whose fields are already built by a function both lines call.

## Trail

- 2026-08-20: Filed by the close of
  [325](325-a-raised-message-is-also-a-logged-one.md), whose proposal was traced and held at one of
  its six sites. That one is closed (the supervisor's survived-SIGKILL failure is raised and no
  longer logged, both of its callers logging what they catch); these five are what is left, with
  the cheaper option now ruled out rather than merely unweighed.

- 2026-09-09: swept, and the trigger had already fired. The rule this entry waits on is worth
  writing now, so it is actionable rather than deferred, and the count in it is six rather than
  five. The sixth site is `check_tool_call_deadline` in
  `brain/packages/orchestrator/src/cortex_orchestrator/bounds.py`, which landed 2026-08-21, one day
  after this entry was filed. The five it names all still stand, read off the tree today: two in
  `residency_moves.py`, two in `residency_watch.py` and one in `swap_builders.py`, each building a
  message, logging it with `extra=`, and raising it. No seventh exists: every site in the brain
  where a name is assigned, passed to a logging call and then raised is one of these six.

- 2026-09-10: Landed as the ADR-0038 logged-and-raised addendum, with the rule the entry asked for
  and its stated blocker reversed. The blocker was that the four `SwapFailedError` sites share a
  catch that "never reads the error's text", so dropping a log there would delete the numbers. That
  was true on the day this was filed and stopped being true two days later:
  [R-350](350-a-failed-swap-in-says-nothing-brain-side.md) landed 2026-08-22 and
  `swap_conductor._swap` now passes `str(err)` to `HandoffSettler.fail`, which writes the whole
  sentence to the handoff record and logs it as the `reason` field of a `WARNING` from
  `cortex_core.swap_settle`. The other two raise into `run_from_env` under `asyncio.run` with
  nothing guarding it, so the traceback carries the sentence. At all six sites the self-contained
  text therefore already reaches a reader by a channel that is not the site's own log call, which
  is what makes a constant message there cost nothing.

  So each site now writes two strings: a constant message for the log call and the full sentence
  for the `raise`. What holds the pair together is an invariant on the fields rather than a gate,
  since the two strings say deliberately different things and a comparison between them would have
  nothing to compare: every value the exception spells is attached to the log call as a field. Two
  field sets grew to satisfy it, the deadline refusals gaining the three terms of the worst stop
  through a new `ControlBounds.pairing_fields`, and `_pairing` gaining the sidecar count. Measured
  through the shipped formatter, the dispatch refusal's line went from 643 characters carrying four
  numbers twice to 215 carrying each once. Nine mutations over the four affected suites, one per
  message and one per field builder, each failed. What the close opened, that four of these lines
  now attach their fields by a call `logfields.py` cannot read, is
  [R-619](619-four-refusal-lines-attach-their-fields-by-a-call.md).
