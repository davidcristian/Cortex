# A wrapped call's needle holds the name rather than the call

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-15
**Trigger:** a registry mention whose template is the name and a comma alone, which is what a
wrapped call takes. Countable by reading `crosscheck.CONSTANTS` for mentions carrying a `name`
whose template renders nothing but `{name},`, and, for each, counting the bounded matches of the
rendered needle in the file it names: one match is the call, and a second is the needle holding a
spelling that is not the call.

Opened 2026-09-15 by the close of
[R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md), which wrote
the working template into the guard's failure message and left what that template gives up.

The guard on `crosscheck.CONSTANTS` requires, of every registry site a brain log call is handed as
its message, a mention landing on the line that hands the name. Its purpose is what catches the
call later being handed another word: the documents stay tied to the binding, and the mention on
the sink fails when the call stops spending it. `<the call>({name},` serves that purpose, since
nothing but the call spells it. `{name},` is what lands on a wrapped call, and it matches the
identifier followed by a comma anywhere in the file: a tuple, an argument list, a second call.

So on a wrapped call the mention holds less than the guard's sentence claims. The guard's line
check ties the needle to the call on the day the site is registered, and after that the needle
holds only that the name is spelled with a comma after it somewhere in that module. A sink whose
call was reworded to another word, and which goes on naming the binding in a tuple, keeps the
needle found and `check-crosscheck` green.

Nothing in the tree takes that template today: all four wrapped calls are unregistered and the one
registered site, `_MESSAGE` in `cortex_tools/audit.py`, is a call on one line taking the tighter
template. So this is what the close of R-518 chose rather than a fault in it, and the cost lands on
the day somebody registers one of the four.

**What would close it.** Either the registry spelling that folds runs of whitespace, so one
template matches the call whether or not it is wrapped, which overturns the rule in `needles.py`
that a needle is matched as written and is the reader change R-518 weighed and declined; or an
occurrence count on the mention, `occurrences=1`, which turns the looseness into a failure the day
a second spelling of the name appears, at the price of failing on an addition that is not a defect;
or a rule in the guard itself that a mention landing on a wrapped call must be pinned some second
way, which is the guard asking for something the registry has no spelling for.

## Trail

- 2026-09-15: opened by the close of
  [R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md), whose
  mutation table measures both templates on a wrapped fixture and says nothing about what the
  shorter one matches elsewhere in a file.
