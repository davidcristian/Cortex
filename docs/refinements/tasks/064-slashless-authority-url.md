# Slashless authority URL

**Status:** landed 2026-08-11
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

As opened, verbatim: running the
resolver over the table turned up a live spelling on none of its rows: a special scheme whose
authority carries **fewer than two slashes**. `new URL("https:evil.example/pay")` is
`https://evil.example/pay`, and so is the one-slash form, because the same special-authority
states that skip a backslash tolerate a missing slash. Measured against the shipped module rather
than read off the regex: `extract_urls` returns nothing for it and a real streaming filter passes
the reply through untouched under **both** policies, the severe shape a fifth time. It is not
fixable in this area's usual shape, which is why it is an entry and not a row: every widening so
far constrains the spelling of a separator that is present, and this one must admit a separator
that is absent, so the anchor needs a **host-shaped lookahead** it has never needed (`https:`
followed by any non-space run is the prose the fullwidth pass deliberately protected, `https：no
slashes here`). The one precedent is `_DATA_ANCHOR`, a single scheme's MIME shape rather than a
host grammar. Its cost is therefore a false-positive budget to design rather than a table entry to
generate, and it is counted from the day it opened.

**It closed in exactly the shape it predicted, and the budget was the work.** The anchor gained
its first lookahead at what follows a separator, and the rule that lookahead enforces is one
sentence: a host is a **dotted name** or a **bracketed literal carrying a colon**, and nothing
else here counts as one. The dotted name covers every registrable domain, every IPv4 literal and
every IDN, with the dot counting in each reading the resolver has, so the same
`LABEL_SEPARATORS` table the identity folds by now also spells the grammar's dot (imported into
the new `url_spellings.py` so the two cannot disagree about what a dot is), joined by the HTML
references one rendering pass resolves and by the single percent escape a parser decodes inside a
host. That percent reading is the only one in this grammar and it is there on a measurement:
`https:evil%2eexample/pay` resolves to the plain link while the stacked `%252e` is a parse error,
so exactly one level is a reading, and the separator positions still decline the family because a
parser throws on `https%3A//evil.example`. The bracketed literal requires the colon, so an IPv6
address is admitted and `[1]` or `[abc]`, which a parser rejects, are not.
**The budget is the single label, and it is spent on prose.** `https:scheme` really is
`https://scheme/` to a parser, and it is also how a sentence names a scheme, so every one-label
host is declined: `http:foo`, `https:localhost:8080/x` and this repo's own way of writing about a
scheme all stay prose, and so does anything carrying a space, which is the shape the fullwidth
pass protected and which the eighth addendum's own test still guards. The decline costs no exfil
vector, a bare label being registrable under no public suffix. **Two things came with the fix
that the entry did not foresee.** The separator is composed out of the opaque family rather than
a new one, so a defanged bare colon reaches this position too (`http[:]evil.example`, which a
reader refangs and lands on), which would otherwise have been the seventh addendum's bracket
asymmetry a second time; and the identity's authority-slash run went from `+` to `*`, one
character, without which the grammar would anchor the spelling and the default policy would still
hold no identity for it. The streaming hold-back needed a branch of its own, since a buffer
ending at `https:evil.` is neither a match nor a prefix of any separator, verified at every
two-way split point of nine probes under both policies (702 splits) and one character at a time.
Thirteen tests, each mutation-proven with `__pycache__` cleared and each mutation verified
applied. **This close moves the area's count by one**, which is the honest bookkeeping: the entry
was counted from the day it opened, on its own last sentence, so it is counted out on the day it
closes. The tail it was found beside, "mixed/other encodings past percent + HTML", is untouched
and stays open on its class. `urls.py` could not hold a host grammar under the line cap, so the
separator vocabulary moved to `url_spellings.py` in the same commit, the split `url_identity.py`
made for the same reason when the seventh addendum landed.

## Trail

- 2026-08-10: Opened rather than chased when running the resolver over the leftover table turned
  up a live spelling on none of its rows, and counted from the day it opened.
- 2026-08-11: Closed in the shape it predicted as the eleventh ADR-0015 addendum, moving the
  area's count back by one. The index notes it is the only one of these guardrail tails to have
  both opened and closed inside the recommended order it was written into.
