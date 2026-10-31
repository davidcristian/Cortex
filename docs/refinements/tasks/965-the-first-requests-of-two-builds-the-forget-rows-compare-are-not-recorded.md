# The first requests of two builds the forget rows compare are not recorded

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

The [separated pair](../../readings/side-effect-tools-on-remember.md#the-forget-calls-on-a-request-to-remember-separated-pair-the-draws-2026-10-31)
drew `forget_memories` in 1 of 30 draws on the build before tools were left out of a request to
remember, `6b9956582`, and a [later build listing the same tools](../../readings/unasked-tools-listed-on-remember.md#the-draws-2026-10-31)
drew it in 5 of 15. Reading the changes between the two found none to the tool list, a tool's text or
the system message, and that is an assumption until the first requests are compared.

## What to do

1. Record the first request of a `git archive` build of `6b9956582` and of a build that lists both
   tools, with `slot1/proxy.py` from the night's scratchpad or its equal, and compare them.
2. Cite the pair again only after that. Nothing that ships rests on it now: a call on a plain request
   to remember is refused by name, so the rate no longer costs a fact
   ([readings](../../readings/forget-refused-on-remember.md)).

## History

- 2026-10-31: filed from the check of refusing that call, as its third step, which the refusal does
  not depend on.
