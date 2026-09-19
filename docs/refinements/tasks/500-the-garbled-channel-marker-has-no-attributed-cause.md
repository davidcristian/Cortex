# The garbled channel marker that destroys a delegated answer has no attributed cause

**Status:** done 2026-08-30
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

On a server using both shipped reasoning-off flags, 13 draws in 76 of the request a delegated run
really sends wrote 1582 to 4078 characters into the reasoning channel, and 11 of the 13 open with a
fragment of a channel marker, the literal `</channels>`, `t</channell>`, `</chaann>`, `h</cha>`,
`h</c>` or a bare `>`, after which the answer itself is written into the channel in plain prose and
the run comes back cut at the cap with an empty `reply`. On an unflagged twin of that server the
same prompt deliberated on 8 draws of 8 and produced no such fragment: every trace there opens as
ordinary deliberation.

The explanation shipped with the firm-prompt close is that the forced close a budget of zero
performs, which was already measured happening after a thought's start sequence and leaking the word
`thought` into one reply in 58, is being emitted where no thought was open, mangled, and then read
by the server's own parser as a channel switch. It explains all four readings and it is an
explanation: nobody read the handler that writes those markers, and one build was measured.

## History

- 2026-08-29: opened by the close of
  [R-479](479-the-reasoning-budget-held-until-the-prompt-pushed.md), which measured the contrast
  between a flagged server and its unflagged twin and labelled its explanation as one.
- 2026-08-29: [R-495](495-the-forced-thought-can-leak-its-own-start-tag.md) records where this
  explanation is drawn from, the same forced close delivering a start tag as a whole valid answer.
  Its committed probe already prints a leak count, so both entries want one instrument.
- 2026-08-30: closed by ADR-0049, which split the shipped pair into its two flags and attributed the
  marker to one of them. `POST /apply-template` on both builds says the two flags are not one
  setting: the kwarg drops the `<|think|>` the template injects and the budget leaves the prompt
  byte identical to an unflagged server's. Measured one flag at a time, `--reasoning-budget 0` alone
  wrote no reasoning character on 30 draws over two builds, while the kwarg alone reproduced the
  trace, the fragments and the empty reply and matched the shipped pair on 20 of 20 matched seeds,
  so on the pair the budget has no effect. The fragments are this template's own closing marker
  `<channel|>` written with a slash in it. That rules out the forced close, since the kwarg-alone
  case sets no budget anywhere; it rules out the build, the same interaction appearing on the build
  the origin measured; and it rules out the cap by position, the fragment being at character zero of
  the trace. What is left is the parser step, why an unmatched close takes the whole answer into the
  channel, which is inference from the marker's shape and is recorded in ADR-0049 rather than as its
  own entry. Opened by this close:
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md), the repair, and
  [R-512](512-no-committed-probe-splits-the-reasoning-off-pair.md), the probe half.
