# A forget request with no call is recorded

**Status:** done 2026-10-30
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`memory_withheld` (`memory_claim.py`), the check `record_exchange` and the reply note share, holds
for a turn whose model named `forget_memories` in a call, whatever happened to the call, through
`TaintLedger.forget_asked`, which the handoff record keeps for the deep phase. A turn whose model
makes no call is recorded with the value in its query, and its reply often says the opposite. In
the 2026-10-30 draws ([readings](../../readings/forget-request-wordings.md)), `Don't save this
anywhere, it's private: my PIN is 5521.` and `Just between us, and not for your memory: my locker
code is 7319.` made no call in 12 of 12 draws, and a forget asked beside another request (`Can
you suggest a quick pasta recipe? Also, don't keep my locker code 7319.`) in 5 of 12. All 17
stored the value. Eleven replies said it would not be kept and one said it was removed.

## What to do

1. Find a wording of a forget request that makes no call. Done on 2026-10-30: rows W03, W04, P01
   and P02 of the readings.
2. Decide the no-call case. Two typed checks could each be one more input to `memory_withheld`:
   one of the query, for a request not to keep or to forget a value, and one of the reply, for a
   statement that something will not be kept or was removed, in the way `claims_kept` reads a
   claim that something was noted. The reply check reads the model's own words and would have
   seen 12 of the 17 no-call draws; the four W03 replies said nothing about the code, so only a
   query check sees those. Either one widens the skip, so its rows include the requests to
   remember of [forget-card-on-remember.md](../../readings/forget-card-on-remember.md), which must
   still be stored, beside W03, P01 and P02. The rows and the rule are written and the
   baseline is drawn
   ([readings](../../readings/forget-request-wordings.md#a-check-of-the-no-call-case-rows-and-rule-2026-10-30)):
   P01 and P02 passed in 0 of 12 draws, and the requests to remember failed in 10 of 32. Build a
   candidate and draw it against them.

## History

- 2026-10-28: filed from the second audit of the forget tool.
- 2026-10-28: a call the model names now marks the turn whether it was refused for the budget
  or the round's size, cut from its round or written as unreadable JSON, and the mark survives a
  handoff; the no-call case remains.
- 2026-10-29: 30 draws of ten wordings of a forget request naming a value, and 70 forget requests
  drawn earlier that night, all called `forget_memories`, so the no-call case has no row yet. Left
  open.
- 2026-10-30: 51 draws of thirteen more wordings. A request, in the message that gives a value,
  not to keep it made no call in 12 of 12 draws, and a forget beside another request in 5 of 12;
  all 17 stored the value. Step 1 is done.
- 2026-10-30: step 2's rows and pass rule were written and its baseline drawn; the candidate is
  left for the next slot.
- 2026-10-30: done. `memory_withheld` now reads the turn's message through `asks_not_kept`
  (`memory_request.py`), so a request not to keep, to forget or to remove something stores
  nothing with or without a call. P01 and P02 passed in 6 of 6 draws each, and the requests to
  remember failed in 9 of 32 against 10 of 32, every failure a forget call
  ([readings](../../readings/forget-request-wordings.md#a-check-of-the-no-call-case-the-candidate-2026-10-30)).
