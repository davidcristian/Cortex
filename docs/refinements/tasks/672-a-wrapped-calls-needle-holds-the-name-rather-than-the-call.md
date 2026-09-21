# A wrapped call's search text matches the name rather than the call

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)
**Verified:** 2026-09-19
**Trigger:** a registry mention whose template is the name and a comma alone, which is what a
wrapped call takes. Countable by reading `crosscheck.CONSTANTS` for mentions with a `name` whose
template renders nothing but `{name},`, and, for each, counting the bounded matches of the rendered
search text in the file it names: one match is the call, and a second is the search text matching
something that is not the call.

The rule on `crosscheck.CONSTANTS` requires, of every registry site a brain log call is given as its
message, a mention that falls on the line passing the name. Its purpose is to catch the call later
being given another word: the documents stay tied to the binding, and the mention on the sink fails
when the call stops using it. `<the call>({name},` serves that purpose, since nothing but the call
writes it. `{name},` is what a wrapped call takes, and it matches the identifier followed by a comma
anywhere in the file: a tuple, an argument list, a second call.

So on a wrapped call the mention checks less than the rule's own sentence claims. The line check
ties the search text to the call on the day the site is registered, and after that it only checks
that the name appears with a comma after it somewhere in that module. A sink whose call was reworded
to another word, and which goes on naming the binding in a tuple, keeps the search text found and
`check-crosscheck` green.

Nothing in the tree takes that template today: six of the brain's fourteen log calls given a bare
name are wrapped, none of the six is registered, and the one registered site, `_MESSAGE` in
`cortex_tools/audit.py`, is a call on one line that takes the tighter template. So this is what the
earlier close chose rather than a fault in it, and the cost arrives on the day somebody registers
one of the six.

**What would close it.** Either a registry form that folds runs of whitespace, so one template
matches the call whether or not it is wrapped, which overturns the rule in `searchtexts.py` that a
search string is matched as written; or an occurrence count on the mention, `occurrences=1`, which
turns the looseness into a failure the day a second occurrence of the name appears, at the price of
failing on an addition that is not a defect, and which costs nothing on registration day, since each
of the six wrapped names is followed by a comma exactly once in its module, at the call; or a rule
requiring a mention on a wrapped call to be fixed some second way, which asks for something the
registry has no form for.

## History

- 2026-09-15: opened by the close of
  [R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md), whose
  mutation table measures both templates on a wrapped fixture and says nothing about what the
  shorter one matches elsewhere in a file.
- 2026-09-19: checked, with one count repaired and the second fix priced. The trigger has not fired:
  of the 313 mentions `crosscheck.CONSTANTS` has, 24 have a `name`, and none of their templates is
  `{name},` alone. The body said four wrapped calls; there are six of fourteen now, the two new ones
  both from 2026-09-17, `_REDACTED_LOG_MSG` in `cortex_core/turn_output.py` and `_GAP` in
  `cortex_tools/audit_file.py`, and still none of the six is registered. The bounded search text
  `{name},` rendered for each of the six matches once in its module, on the line passing it to the
  call, so an `occurrences=1` mention would pass on registration day for any of them. The rule's
  docstring and the comment above its wrapped fixture in `scripts/tests/test_crosscheck.py`, and the
  sentence describing it in [repo-checks.md](../../modules/repo-checks.md), still counted four of
  twelve, and the docstring gave the odds that followed from it; all three now say only that wrapped
  calls are common.
