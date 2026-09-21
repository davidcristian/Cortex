# ADR-0040: Plain prose in code, documentation and commit messages

**Status:** Accepted (2026-09-19)

## Context

Prose here is read by people who have never seen this repository, and written mostly by agents.
Both facts pull the same way. A figurative vocabulary, in which code `spells` a value, a record
`carries` a fact, a change `lands` and a test `pins` a number, costs a reader a translation step
before every sentence, and none of those words means what it says. Long docstrings and comments
cost the same reader the opposite way: a docstring longer than the function it heads is skipped,
so the one line that mattered is skipped with it.

The style copies itself, because every agent writes from the sample in front of it, and AGENTS.md
is part of that sample. A rule nothing reads the tree for therefore drifts, whatever it says.

## Decision

The Prose section of [AGENTS.md](../../AGENTS.md) states the rule and is the copy to read. This
record says what it is and why.

1. **Comment only what the code cannot say.** A comment is necessary when it gives a reason the
   code has no room for: why a workaround exists, a constraint that is not visible (an ordering,
   a link to a specification or bug, a measured number the code depends on), or a directive a
   tool reads. A comment that repeats the code, tells history, cites a decision record for
   background, or explains what a better name would say is deleted. One or two lines, three at
   most.
2. **A docstring is one line.** It says what the module, class or function does. A second or
   third line is added only when an argument or a return value is not obvious from its name and
   type, and never a fourth. A docstring that only repeats the name is deleted, and test
   functions and test modules have none, because the test name says what it checks. Design
   reasons belong in a decision record or a module doc, and history belongs in git.
3. **Every sentence names its subject and says what it does.** No opening riddle, and no
   withholding the subject for effect.
4. **Code has no intentions.** A check passes, fails, reads, writes, returns or raises. It does
   not know, notice, want, refuse or believe.
5. **No metaphor outside a designed name.** A naming family built under the naming rule in the
   working agreement may be figurative, because its entries are labels and its structure means
   something: the mark's Mull, Muse, Hunch and Tangent, the window's Still, Lucid, Reverie and
   Trance, and `RankBasis`, which is internal and qualifies on the same terms because it is
   defined in full where it is introduced: renaming its members to `COSINE`, `RECENCY` and the
   rest would change 48 call sites and lose the pairing the enum exists to show. A metaphor may
   be a label. It may never be the explanation of a mechanism.
6. **No aphorisms.** State the consequence rather than coining a maxim about it.
7. **Define a technical term once, where it first appears, then use it.** A precise term is
   welcome; a figurative word used in place of a technical one is not.
8. **No machine tics.** Runs of short parallel fragments, the "not X, but Y" reversal,
   throat-clearing openers, inflated stakes, stock intensifiers, and a closing sentence that
   restates the paragraph above it.
9. **Clarity first, and cut what nobody needs.** Cut the story of how the code got here, repeated
   explanations (link to the one place instead) and hedging. Do not cut a sentence until it needs
   a second reading.
10. **Write a measurement a reader on other hardware can use.** A figure that describes only the
    machine it was taken on is written as a ratio of that machine's own numbers: a power draw as
    a fraction of the card's own limit, an SM clock as a fraction of its own maximum. Where an
    operator takes the reading themselves, the sentence names the fields they query
    (`enforced.power.limit` against `power.max_limit`) rather than the values this machine
    returned. A figure stays absolute when a reader compares it directly with their own hardware
    to decide whether something fits: the card's memory, a model's weights, a context size, the
    VRAM cap. A timing in seconds stays absolute too, with the sentence around it saying under
    what conditions it was taken. A temperature stays as read, because a ratio needs the card's
    own threshold beside it and a reading rarely has one.
11. **A table of banned words, and two checks that read it.** The Prose section of AGENTS.md has a
    table whose left column lists words this repo does not use and whose right column gives what
    to write instead. `scripts/prosecheck.py` reports every use in markdown, comments and
    docstrings, and `scripts/commitlint.py` refuses a commit message that uses one. Both run on
    every change, the first in `just check` and in CI, the second at the `commit-msg` stage. A
    word matches whole and in any case, and the words of a phrase may be split by one line break.
    Text in backticks, link targets, URLs, string literals and pastes are not searched, which is
    how a file name, an identifier, a command and the `seam` package stay writable. The table is
    a minimum rather than the whole rule: any other figurative word is rewritten the same way.
12. **A docstring and a comment block are at most three lines, counted by the same tool.** A
    comment block is a run of lines that hold only comments; a line that holds code ends it and a
    blank line does not. Every line of a `/* */` comment that spans several lines belongs to the
    block, even when code shares its first or last line. A line counts when its text, without the
    comment markers, is not empty and is not a directive, so a shebang, a coding line, a `noqa`,
    a `pragma` and their kin cost nothing. A docstring counts the source lines between its quotes
    that hold text other than quotes and whitespace.
13. **Every markdown file is at most 250 lines**, except the two generated backlog indexes.
    `scripts/linecap.py` checks it. An index is exempt only while it still contains the comment
    `just backlog` writes above the block it generates.
14. **A commit message body is at most 50 words.** The subject says what changed and the body says
    why it was needed, in two or three sentences a reader takes in at a glance. A body with room
    to argue its case argues it in the place nobody rereads, so longer reasoning belongs in a
    decision record or a module doc and the message points there. `scripts/commitlint.py` counts
    the words outside a fence or a paste ([ADR-0026](ADR-0026-prose-style-checks.md)).
15. **The table reaches every name a reader meets in hand-written code.** That is identifiers
    (constants, classes, functions, arguments, and locals that are public or widely read), the
    words of a log message and its field names, test function names, and prose fields such as a
    Cargo `description`. It stops at a name fixed outside the code: an environment variable
    (`CORTEX_SWAP_TIER_HEAL_S` and `CORTEX_SEAM_TOKEN` stay, because a deployment's configuration
    sets them), a proto message, field or package name (`cortex.seam.v1`), the `cortex_seam`
    package, a key in recorded data (the envelope samples' `arm`), and anything the Windows host
    reads. An identifier beside a kept name may still be renamed: a settings field keeps its
    variable as a `validation_alias`. No check reads identifiers, so a `git grep` survey finds the
    rest, and the backlog lists what is left. Backlog file names are a task of their own.

## Consequences

- The checks cover the mechanical half of the rule: a word from the table, and a docstring or
  comment block that is too long. Decisions 3 to 9 are read by a person in review, as imperative
  mood in a commit subject already is.
- The backlog's own grammar is written in the plain words rather than exempted from the table: a
  closed task reads `done <date>`, an open one `waiting for its trigger` or
  `waiting for a consumer`, an optional capability is an `optional feature`, a task that needs a
  port change first says so, an ongoing state is `ongoing`, the host field is `Session`, and a
  task's own record of what happened is its `## History` section.
- A word in the table is sometimes literal: the overlay's own feature is `pin`, and a processor
  may be `arm64`. Backticks around the identifier, or a rewording such as "keep a chat at the top
  of the list", is the way through. There is no per-line exemption marker.
- Five other checks read prose, so editing a sentence is a change that must pass `just check`
  rather than a text substitution: `rostercheck.py` reads the lists documents keep,
  `samplecheck.py` the log lines runbooks print, `stubcheck.py` the comments in
  `proto/body.proto`, `backlogcheck.py` headings and every `#fragment`, and `crosscheck.py` the
  values quoted inside prose.
- A name decision 15 covers is renamed as a code change rather than a prose edit, together with
  the runbook line, module doc and task files that quote it. A name it excludes keeps its word.

## Alternatives rejected

- **A check for code given intentions.** A list of volition verbs against a closed set of nouns
  was written during the 2026-09-13 review: 953 candidates at an estimated 30 percent false
  positives. A check that is wrong one time in three is a check people turn off.
- **A per-line exemption marker**, the way `dashcheck: allow` works for a dash that means rather
  than punctuates. A banned word almost always has a plain replacement, and backticks already
  cover the case where the word is a name.
- **Rules without a table.** A rule stated in prose alone has nothing that reads the tree for it,
  so nothing fails when the prose drifts and the rule becomes advice.

## Related

- [AGENTS.md](../../AGENTS.md), the Prose and Commits sections: the rule itself
- [ADR-0026](ADR-0026-prose-style-checks.md): the dash ban and the commit-message checks beside it
- [The module doc for `scripts/`](../modules/repo-checks.md): what `prosecheck.py` and
  `commitlint.py` read and report
- [R-663](../refinements/tasks/663-a-figure-that-describes-only-this-machine-is-caught-by-eye.md):
  whether decision 10 can be checked by a machine
- [R-699](../refinements/tasks/699-source-file-names-use-banned-words.md),
  [R-700](../refinements/tasks/700-backlog-file-names-use-banned-words.md),
  [R-701](../refinements/tasks/701-keeping-a-chat-at-the-top-has-no-designed-name.md) and
  [R-705](../refinements/tasks/705-names-inside-files-still-use-banned-words.md): names that still
  hold a word from the table
