# Withheld unasked tools may raise forget calls on a remember request

**Status:** done 2026-10-31
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

On a request to remember, `unasked_tools` (`unasked_tools.py`) leaves `set_volume` and
`schedule_task` out of the tool list. In
[side-effect-tools-on-remember.md](../../readings/side-effect-tools-on-remember.md) the requests
to remember R01 to R15 called `forget_memories` in 5 of 30 draws before that change, 12 of 30
after it, and 8 of 30 in a replication on the build after it, which is no result under the rule
written before it. Each such call matched nothing and the fact was kept.

## What to do

1. Write a separated pair into the readings before drawing it: a `git archive` build of the
   commit before the change and one of the change, R01 to R15 twice each on each build, the two
   builds drawn in turn so a run's drift cannot pass for the change's effect, with a rule for
   what difference counts.
2. Change nothing on these rows until that pair is drawn.

## History

- 2026-10-30: filed from the replication of the forget calls on a request to remember.
- 2026-10-31: done. The pair drew 1 of 30 before the change and 13 of 30 after it, a difference of
  12 against a bound of 7, so the change raised the forget calls and the earlier counts were not
  drift. The rule leaves the withheld tools in place and files
  [R-961](961-leaving-tools-out-of-a-request-to-remember-raises-forget-calls.md). This entry said
  the person is shown a forget card; none of the 39 calls in the four runs showed one, since a
  call that matches nothing has no card.
