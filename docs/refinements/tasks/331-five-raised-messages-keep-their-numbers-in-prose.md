# Five messages that are raised and logged still spell their own numbers

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** a sixth site of this shape arriving, or one where the prose value and the field beside
it disagree
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Five sites build one string, log it, and raise it as a typed error's text, so the line an operator
sees carries a value in the prose and again on the right:
`residency_moves._refuse_a_load_the_card_cannot_hold` twice, for a card that reports nothing and
for one that is short; `residency_watch` twice, for the daemon that could not be converged and for
the fresh sidecar whose worst stop the deadline no longer clears; and `swap_builders`, for the
deadline pairing the composition root refuses to serve on.

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

That is why the trigger is what it is. A sixth site is worth a rule; a site where the two spellings
have already drifted is worth the fix on its own, because a drifted pair is the exact harm the
second string risks and the only evidence that the risk is real here.

## Trail

- 2026-08-20: Filed by the close of
  [325](325-a-raised-message-is-also-a-logged-one.md), whose proposal was traced and held at one of
  its six sites. That one is closed (the supervisor's survived-SIGKILL failure is raised and no
  longer logged, both of its callers logging what they catch); these five are what is left, with
  the cheaper option now ruled out rather than merely unweighed.
