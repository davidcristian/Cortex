# A work identity is copied by hand at every hop and nothing ties the copies

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** a fifth work identity arriving on `TurnStamp`, or a hop found dropping one of the
four that are there.

Four work identities now reach an audit line: the chat, the conversation turn, the subagent task,
and the scheduled item whose fire made the dispatch. Getting one from a fire to the work it caused
is six hand-written copies: the caller's `TurnStamp`, `SpawnSubagentsTool` reading it off the call
onto `SubagentTask`, the Redis codec's encode and its decode, `PlacedAttempt` reading it back into
its `ToolLoopContext`, and `_stamp` putting it on every dispatch the delegate makes. Nothing
structural ties the six. A new identity can be added to the stamp and stop at any of them, and the
only thing that catches it is a test written for that identity end to end.

The bundle that would have tied them was weighed when the item landed and declined, and the
argument is in the ADR: these four are independently present or absent, every combination is a
caller this tree really has, so a value object would exclude no invalid state, and the same four
are deliberately flat on `TurnStamp` and on `ToolInvocation`, so bundling the loop context alone
buys a translation at each end. That argument is about four. **A fifth is what would change it**,
which is why this is filed with that as its trigger rather than closed as decided.

Two cheaper answers exist and neither needs a bundle. One is a test that enumerates the identity
fields of `TurnStamp` and asserts each reaches `ToolInvocation` and each survives the task record,
so a field added to one and forgotten at another hop makes a test fail without anyone having
written a case for it.
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
