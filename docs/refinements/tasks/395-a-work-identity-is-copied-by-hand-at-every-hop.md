# A work identity is copied by hand at every hop and nothing ties the copies

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
**Trigger:** a fifth work identity arriving on `TurnStamp`, or a hop found dropping one of the
four that are there.

Four work identities now reach an audit line: the chat, the conversation turn, the subagent task,
and the scheduled item whose fire made the dispatch. Getting one from a fire to the work it caused
is six hand-written copies: the caller's `TurnStamp`, `SpawnSubagentsTool` reading it off the call
onto `SubagentTask`, the Redis codec's encode and its decode, `PlacedAttempt` reading it back into
its `ToolLoopContext`, and `_stamp` putting it on every dispatch the delegate makes. Two more
carry it from that dispatch to the line: `ToolDispatcher._audited` in `cortex_core/dispatch.py`
copies the stamp's four onto `ToolInvocation`, and `invocation_fields` in `cortex_tools/audit.py`
names each under its log field, the one list both audit sinks write. Nothing structural ties the
six, or the eight. A new identity can be added to the stamp and stop at any of them, and the
only thing that catches it is a test written for that identity end to end.

The bundle that would have tied them was weighed when the item landed and declined, and the
argument is in the ADR: these four are independently present or absent, every combination is a
caller this tree really has, so a value object would exclude no invalid state, and the same four
are deliberately flat on `TurnStamp` and on `ToolInvocation`, so bundling the loop context alone
buys a translation at each end. That argument is about four. **A fifth is what would change it**,
which is why this is filed with that as its trigger rather than closed as decided.

Two cheaper answers exist and neither needs a bundle. One is a test that enumerates the identity
fields of `TurnStamp` and asserts each survives the task record and each reaches the record
`invocation_fields` builds, so a field added to one and forgotten at another hop makes a test fail
without anyone having written a case for it. `ToolInvocation` is not far enough: a field that
reaches it and is left out of `invocation_fields` reaches neither audit sink. The test has to pick
the identities out of `TurnStamp` somehow, and the four are its only `str` fields today.
The other is to leave it and keep paying a per-identity end-to-end case, which is what the item's
own arrival paid. Read both against the cost of the next arrival before choosing.

The measurement to weigh them against is in the ADR's own sweep: of the five mutations that landed
the fired item, three made no test fail but that single end-to-end case, one made the store's
contract fail and one the codec's corrupt-record case. So the per-identity case does hold the chain
today, and what it does not hold is an identity nobody wrote a case for.

## Trail

- 2026-08-23: Opened by the close of
  [380](380-a-fires-delegates-do-not-name-the-item.md), which asked whether the identities should
  travel as one value, declined the bundle on the criterion above, and counted the hops the
  decline leaves hand-written. Recorded in the ADR-0009 fired-work addendum.
- 2026-09-07: trigger re-derived against the tree and neither half has fired. `TurnStamp` in
  `brain/packages/core/src/cortex_core/tools.py` still carries exactly the four work identities
  this entry counts, `session_id`, `turn_id`, `task_id` and `item_id`; its other five fields are
  the taint bit, the provenance tuple and the three live handles (`budget`, `progress`,
  `escalation`), none of which name work. No hop drops one either: `SpawnSubagentsTool` in
  `spawn.py` writes the three a task stores off the call's stamp, `_encode_task` and `_decode_task`
  in `cortex_session/tasks.py` round-trip all three, `PlacedAttempt` in `subagent_attempt.py` reads
  all four back into its `ToolLoopContext` (`turn_id` from the stored task, on the line above the
  comment that explains the other three), and `_stamp` in `dispatch_round.py` puts them on each
  dispatch. Every symbol the entry names still lives in the file it names, so its counts hold.
  Recorded in the ADR-0009 addendum of this date.
- 2026-09-13: re-derived and left open. Neither half of the trigger has fired. `TurnStamp` in
  `brain/packages/core/src/cortex_core/tools.py` still carries exactly four work identities,
  `session_id`, `turn_id`, `task_id` and `item_id`, beside the taint bit, the provenance tuple and
  the three live handles, so no fifth has arrived. No hop drops one either: `SpawnSubagentsTool`
  writes the three a task stores off the call's stamp at `spawn.py:201`, `_encode_task` and
  `_decode_task` in `cortex_session/tasks.py` round-trip those three, `PlacedAttempt` in
  `subagent_attempt.py` reads all four back into its `ToolLoopContext` with `turn_id` on the line
  above the comment that explains the other three, and `_stamp` in `dispatch_round.py` puts them on
  each dispatch. The six hops the entry counts are still six.
- 2026-09-19: re-derived and left open, the hop count and the test the entry proposes both
  repaired. Neither half of the trigger has fired: `TurnStamp` still carries the same four
  identities beside the same five other fields, and every hop still copies all of them, at
  `spawn.py:201`, in `_encode_task` and `_decode_task`, at `subagent_attempt.py:187` for `turn_id`
  and `:196` to `:198` for the other three under the comment explaining them, and in `_stamp` at
  `dispatch_round.py:143`. The six copies stop at the dispatch, though, and the title's claim is
  about the audit line, which two more hand-written hops reach: `ToolDispatcher._audited` at
  `dispatch.py:286` and `invocation_fields` in `cortex_tools/audit.py`. The second existed inside
  `LoggingAuditSink.record` when this entry was filed and moved into a shared function when the
  audit trail gained its file, which both sinks spend, so the file added no ninth copy. The test the
  entry offered asserted arrival at `ToolInvocation`, one hop short of both sinks, and now names the
  record `invocation_fields` builds. Recorded in the ADR-0009 shipped-pair addendum.
