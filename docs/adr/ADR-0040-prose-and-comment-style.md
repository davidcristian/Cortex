# ADR-0040: Prose style for code, documentation, and commit messages

Date: 2026-08-31. Status: accepted.

## Context

The repo's prose had drifted into a register that costs a reader time. A commit subject and body
could be read in full without yielding what the change did.

The drift is measurable. Every docstring, comment, and markdown paragraph in the tree was
extracted and scored for four constructions: personification of code artifacts, metaphor nouns,
sentences that withhold their subject, and abstract deixis.

| tree | files with hits | prose lines | hits | per 100 lines |
| --- | --- | --- | --- | --- |
| `scripts/` | 60 | 3,993 | 441 | 11.0 |
| `scripts/tests/` | 36 | 1,653 | 190 | 11.5 |
| `docs/refinements/` | 420 | 22,352 | 1,507 | 6.7 |
| `brain/` | 300 | 21,828 | 1,335 | 6.1 |
| `docs/adr/` | 38 | 40,977 | 2,431 | 5.9 |
| `body/app/` | 89 | 4,264 | 255 | 6.0 |
| `docs/modules/` | 15 | 8,776 | 491 | 5.6 |
| `body/crates/` | 39 | 3,153 | 169 | 5.4 |

Sentence length is not the defect. With list items counted separately, medians run 14 to 20 words
across every tree, which is normal technical prose. The defect is vocabulary and construction:

1. **Personified artifacts.** `scripts/switchtail.py` called itself "the reader that notices" and
   described a reader as "the least likely person here to notice". A gate does not notice.
2. **Aphorism in place of a statement.** `scripts/values.py` explained a refusal with "a reducer
   that guesses is a gate that agrees with itself". The reader has to reconstruct the mechanism
   from the maxim.
3. **Metaphor doing the work of explanation.** An unrecognized chat-template format was "a third
   family's spelling"; the absence of a closing thought marker was "the open door". Neither term
   appears in any specification, so neither can be looked up.
4. **Riddle openers.** Every module docstring in `scripts/` withheld its subject: "What a value IS
   to the scans that compare one", "Whether a tier's rendered prompt still predicts what its
   constrained cell did". None said what the file does.

Docstrings had also grown to 34 to 45 percent of the files in `scripts/`, with a 56-line module
docstring standing before the first import in `switchtail.py`.

The style reproduces itself, because AGENTS.md models it. Gate 6 was a single 887-word sentence,
and the repo map's `scripts/` block was a comma-spliced run of 546 words. Every module docstring
and every commit message was written by someone who had just read that file.

Commit subjects show the same pattern. Across 674 commits the leading verb was `hold` 43 times and
`record` 39 times, against 67 total uses of the plain verbs of change (`add`, `fix`, `remove`,
`split`, `rename`, `update`). "hold the trail reader's needles to the sink" does not tell a reader
what changed.

## Decision

**AGENTS.md gains a `## Prose` section, which is the canonical statement of the rule.** The
substance:

1. Comment only what the code cannot say. A comment explains a non-obvious why: a workaround, a
   spec citation, an ordering constraint, a measured number, a rejected alternative.
2. Docstrings are short. One line on what the module or function does, plus arguments and returns
   where those are not obvious. Design reasoning moves to `docs/modules/` or to the ADR that
   decided it. Ten lines is the practical ceiling.
3. Every sentence names its subject and says what it does.
4. Code has no intentions. A gate passes, fails, reads, writes, returns, or raises.
5. No metaphor outside a designed naming family, defined where it is introduced.
6. No aphorisms. State the consequence.
7. Define jargon once at first use, then use it. Precise terms are welcome; figurative substitutes
   for technical terms are not.
8. No AI-isms. Runs of short parallel fragments, the "not X, but Y" reversal, throat-clearing
   openers, inflated stakes, stock intensifiers, and closing sentences that restate the paragraph.
9. Clarity is the target, not brevity. A sentence cut until it needs a second reading has failed
   the rule twice.

**Designed naming families are the one exemption**, and they were already governed by the naming
rule in the working agreement: the mark's Mull, Muse, Hunch, and Tangent, and the window's Still,
Lucid, Reverie, and Trance. A metaphor may be a label. It may not be the explanation of a
mechanism. `body/app/src/mark/marks.ts` is the worked example: the labels carry the metaphor and
the comment above them is plain.

The exemption first read "the naming families a user sees", which was written with pickable UI
styles in mind and made an internal family look like a violation. `RankBasis` is the case that
found it: `ECHO` and `EMBER` are raw likeness and the recency-warmed blend, `SPREAD` and `SWEEP`
the MMR objective over each, and `VERDICT` and `DEMUR` are judicial on purpose, marking where the
model decided rather than a heuristic. That structure is the finding the enum exists to carry, it
is defined in full where it is introduced, and it appears in the recall trail an operator reads.
Renaming it to `COSINE`, `RECENCY`, `MMR_RAW` and the rest would spend 48 call sites to lose the
pairing. The rule now turns on whether a family is designed and defined at first use, not on who
reads it.

**Commit messages state what changed and why it was needed.** The subject leads with a verb of
change and names what changed. The body gives the problem, then the change.

**The whole corpus is brought to the rule, and all commit messages are rewritten.** The repo is
private and unshared, so rewriting history costs nothing beyond the rewrite itself. Leaving the
existing corpus in the old register would leave every future agent a larger sample of the style
being replaced than of the one being adopted.

**No gate enforces this**, which is a deliberate exception to the rule that a convention without a
gate is a defect. Personification is partly detectable, and a curated deny-list of volition verbs
against a closed set of artifact nouns was prototyped during the review: it found 953 candidates
with an estimated false-positive rate near 30 percent. The other four rules are not mechanically
detectable at all. A gate that fires on correct prose one time in three gets bypassed, and a gate
covering only the detectable fifth of a rule would report the rule as satisfied when it is not.
This joins imperative mood as a convention enforced by review. The line-cap and docstring-length
pressure that `linecap.py` already applies is the closest mechanical proxy and is left as it is.

## Consequences

- AGENTS.md gate 6 and the repo map's `scripts/` block are rewritten as lists. Both sit inside
  passages `rostercheck.py` bounds, so the anchor phrases and every member name survive the
  rewrite unchanged.
- Prose in this repo is load-bearing for five gates: `rostercheck.py` reads roster passages,
  `samplecheck.py` reads runbook log samples, `stubcheck.py` reads proto comments,
  `backlogcheck.py` reads headings and every `#fragment`, and `crosscheck.py` reads values spelled
  inside prose. A prose sweep is a gated change, not a text substitution, and runs against
  `just check` throughout.
- The sweep removes comments rather than rewriting them wherever the code already says it. Files
  get shorter, which the line cap welcomes and coverage does not notice.
- Rewriting 674 commit messages changes every hash. The pre-rewrite history is kept at the
  `prose-review-backup` tag until the result has been reviewed.
- ADRs keep their addenda. The sweep reaches their prose but does not re-argue or renumber
  decisions, and an addendum's dated record of what was measured stays as written.
