# A rank fallback cannot name its turn

**Status:** landed 2026-08-20
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`JudgeRecallPolicy.select` now warns when it falls back to geometry, and the warning names the pool
it gave up on and the `k` asked of it and nothing about where it happened. It cannot: `RecallPolicy`
is `candidate_k(k)` plus `select(hits, *, query, now, k)`, and no session id, turn id or nonce
crosses that port. The pool and the query are all a policy is handed, and the query is conversation
content that no line may carry.

Everything beside it names one. `SummarizingHistoryWindow` logs `session_id` with its boundary,
`_report_forgone_memory` logs `session_id` and `turn_id`, and `LoggingRecallSink` writes `session`
on the very trail line an operator would pair a fallback with. So on a brain serving several
conversations, a burst of rank fallbacks cannot be attributed to one of them, and a fallback cannot
be tied to the recall whose trail line sits beside it in the same log.

The cost is the port, which is why this is filed rather than folded into the line. `select` gains a
caller-supplied identity, and the right shape is the one `drain_text` took for its ledger: an
optional collaborator, so the five policies that never log are unchanged and a policy that does
takes what it needs. A required positional would touch `RawRecallPolicy`, the three heuristic
policies, `MemoryRecaller.recall`, every fake in the core tests and the composition root, for a
field four of the five ignore. Note that `MemoryRecaller.recall` already holds the `session_id`, so
nothing new has to be plumbed to reach the port; only the port has to accept it.

## Trail

- 2026-08-19: Opened by the close of [R-309](309-a-silent-judge-fallback.md), which gave the judge
  its two fallback warnings and found they could say what happened and never to whom.
- 2026-08-20: Landed as the shape this entry named. `select` grew a keyword-only
  `session_id=None`, the recaller passes the id it already held, and both warnings carry it as
  `session`, the spelling the recall trail uses so the two lines pair. Two things the entry got
  wrong are worth recording: the four policies that never log are **not** untouched, since a
  Protocol method's parameter list binds every structural implementation, so all four take the
  keyword and delete it, as `CharBudgetHistoryWindow` does for `progress`; and the four test fakes
  had to take it too, which is the cost the optional shape saves at the call sites and does not
  save at the implementations. Recorded in the ADR-0038 named-recall addendum, which also files
  the turn id this entry's title asked for and the two spellings the field name now leaves behind.
