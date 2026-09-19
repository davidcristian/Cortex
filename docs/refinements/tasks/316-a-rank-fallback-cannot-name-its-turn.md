# A rank fallback cannot name its turn

**Status:** done 2026-08-20
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`JudgeRecallPolicy.select` warns when it falls back to geometry, and the warning names the pool it
gave up on and the `k` asked of it, and nothing about where it happened. It cannot: `RecallPolicy`
is `candidate_k(k)` plus `select(hits, *, query, now, k)`, and no session id, turn id or nonce
crosses that port. The pool and the query are all a policy receives, and the query is conversation
content that no log line may include.

Everything beside it names one. `SummarizingHistoryWindow` logs `session_id` with its boundary,
`_report_forgone_memory` logs `session_id` and `turn_id`, and `LoggingRecallSink` writes `session`
on the recall trail line an operator would read next to a fallback. So on a brain serving several
conversations, a burst of rank fallbacks cannot be attributed to one of them.

The cost is the port, which is why this is filed rather than folded into the log line. `select`
gains a caller-supplied identity, best as an optional argument, the way `drain_text` took its
record. `MemoryRecaller.recall` already has the `session_id`, so nothing new has to be passed
through to reach the port; only the port has to accept it.

## History

- 2026-08-19: Opened by the close of [R-309](309-a-silent-judge-fallback.md), which gave the judge
  its two fallback warnings and found they could say what happened and never to whom.
- 2026-08-20: Fixed as described. `select` gained a keyword-only `session_id=None`, the recaller
  passes the id it already had, and both warnings include it as `session`, the same field name the
  recall trail uses so the two lines can be read together. Two things this entry got wrong: the
  four policies that never log are not untouched, since a Protocol method's parameter list binds
  every implementation, so all four take the keyword and discard it, as `CharBudgetHistoryWindow`
  does for `progress`; and the four test fakes had to take it too, which is the cost the optional
  form saves at the call sites and not at the implementations. The decision is ADR-0038 decision
  15; the turn id this entry's title asked for and the two field names left behind were filed as
  R-338 and R-339.
