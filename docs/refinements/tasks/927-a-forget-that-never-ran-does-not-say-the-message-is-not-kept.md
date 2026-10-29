# A forget that never ran does not say the message is not kept

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-29

`ForgetChosenTool.invoke` (`memory_forget_chosen.py`) ends every result with
`FORGET_NOT_KEPT_NOTE`, which tells the model that nothing in the message is kept and that
anything else it asked to be remembered must be sent again. A `forget_memories` call that never
reaches `invoke` gets another text instead: `USER_DECLINED_MSG` when the person presses Deny,
`UNANSWERED_MSG` or `EXPIRED_MSG` when the card goes unanswered (all in `untrusted.py`), or a
`DispatchRefusal` (`dispatch.py`) for the call budget, a repeated call, a call already declined or
a round with too many calls. `record_exchange` (`turn_output.py`) skips that turn too, so a new
fact in the same message is lost and the model is not told. No row has measured these paths; the
readings drew only approved cards ([readings](../../readings/forget-chosen-memories.md#a-forget-and-a-new-fact-the-draws-2026-10-29)).

## What to do

1. Write rows first: row N1 of the readings with the card declined, five draws, under the same
   pass rule.
2. If it fails, add the note to the results a forget call gets when it does not run, in the way
   a tool's own refusal texts are chosen, and ship it only if the rows pass.

## History

- 2026-10-29: filed from the close of task 922, whose note covers only the results `invoke`
  returns.
