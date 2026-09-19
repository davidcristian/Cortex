# A wrapped call's needle holds the name rather than the call

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19
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

Nothing in the tree takes that template today: six of the brain's fourteen log calls handed a
bare name are wrapped, none of the six is registered, and the one registered site, `_MESSAGE` in
`cortex_tools/audit.py`, is a call on one line taking the tighter template. So this is what the
close of R-518 chose rather than a fault in it, and the cost lands on the day somebody registers
one of the six.

**What would close it.** Either the registry spelling that folds runs of whitespace, so one
template matches the call whether or not it is wrapped, which overturns the rule in `needles.py`
that a needle is matched as written and is the reader change R-518 weighed and declined; or an
occurrence count on the mention, `occurrences=1`, which turns the looseness into a failure the day
a second spelling of the name appears, at the price of failing on an addition that is not a defect,
and which costs nothing on the day of registering: each of the six wrapped names is followed by a
comma exactly once in its module, at the call;
or a rule in the guard itself that a mention landing on a wrapped call must be pinned some second
way, which is the guard asking for something the registry has no spelling for.

## Trail

- 2026-09-15: opened by the close of
  [R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md), whose
  mutation table measures both templates on a wrapped fixture and says nothing about what the
  shorter one matches elsewhere in a file.
- 2026-09-19: verified, with one count in the body repaired and the second close priced. The
  trigger has not fired: of the 313 mentions `crosscheck.CONSTANTS` carries, 24 carry a `name`,
  and none of their templates is `{name},` alone. The body said four wrapped calls; there are six
  of fourteen handed calls now, the two new ones both from 2026-09-17, `_REDACTED_LOG_MSG` in
  `cortex_core/turn_output.py` and `_GAP` in `cortex_tools/audit_file.py`, and still none of the
  wrapped six is registered. The bounded needle `{name},` rendered for each of the six matches
  once in its module, on the line handing it to the call, so an `occurrences=1` mention would pass
  on registration day for any of them. The guard's docstring and the comment above its wrapped
  fixture in `scripts/tests/test_crosscheck.py`, and the sentence describing the guard in
  [repo-gates.md](../../modules/repo-gates.md), still counted four of twelve, and the docstring
  gave the odds that followed from it; all three now say only that wrapped calls are common, which
  is the fact the second template in the fault rests on.
