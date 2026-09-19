# ADR-0026: Prose style checks (no dash as punctuation, no volatile references)

**Status:** Accepted (2026-08-24)

## Context

Two rules govern the repo's prose, and neither was checked:

1. **No dash as punctuation.** Prose here does not use an em dash.
2. **No volatile references in a commit message.** A message must still read correctly once the
   planning docs move on, so it may not cite a slice number, a decision-record number, the
   roadmap, or any numbered pointer into a mutable doc.

A review of the history found 3452 distinct lines using an em dash across every commit, and 144 of
148 commit messages breaking at least one rule: prose is rewritten constantly, and the dash is the
default output of nearly everything that writes it. `just check` is the single place these rules
can be enforced and it checked neither. The rules are also easy to enforce wrongly: the review's
ad hoc verifier reported an en dash inside a numeric range and the SQL comment marker at the head
of a line, both correct text, and a check that fails on correct text gets turned off. The commit
rules in AGENTS.md add a third checkable rule, the 72-column body wrap, which has to leave pasted
commands and code intact.

## Decision

`scripts/dashcheck.py` is a cross-tree scan in `just check`, run unconditionally in CI like the
line cap, and `scripts/commitlint.py` checks the whole commit message as a commit-msg hook.

### Dashes, hashes and generated headers

1. **The em dash and the en dash are banned outright; U+2212 MINUS SIGN is not.** A range is typed
   with an ASCII hyphen (a 2-4B model, 0.15-0.27 GB), which reads as typed; every en dash in the
   tree was a range and took a hyphen without loss. The minus sign stays legal, since forcing `-`
   on a subtraction would make the arithmetic wrong. A range's hyphen is how a range is written in
   ASCII, not a substitution for a punctuation mark: an em dash punctuates, so its fix is to
   restructure the sentence, never to swap in another mark.

2. **ASCII `--` is banned in a commit message and allowed in a file.** A commit message is prose,
   so ` -- ` there is an em dash written in ASCII. A source file uses `--` to introduce an inline
   reason (`# noqa: DTZ001 -- the naive value under test`, `# pragma: no cover -- reason`), which
   the escape-hatch rule requires. `commitlint.py` applies the strict rule, `dashcheck.py` the
   lax one.

3. **`dashcheck.py` reads every text file, tests and `_generated` included.** A comment in a test
   is prose, and a generated stub repeats the proto's comments word for word; the rule follows the
   prose, not the compiler.

4. **The escape hatch is an inline `dashcheck: allow` plus a reason**, for a dash that is the
   subject rather than punctuation. The repo has one: an HTML test asserting `&#8212;` decodes to
   the literal character. The pragma moves with its subject.

5. **The checks write dashes as `\uXXXX` escapes** in their own source and tests, so a check that
   names a forbidden character does not contain it, and its own files need no exemption.

6. **A commit hash is reported only when it resolves**, through `git cat-file` against the repo. A
   rewrite invalidates a cited hash, which is why the rule exists, but hex strings are also action
   versions and digests. Resolving the token separates the two exactly. If `git` is unavailable
   the check cannot disprove the hash and passes, since a hook blocking a commit because it cannot
   run the check is worse than the miss.

7. **Git-generated headers (`Merge `, `fixup! `, and the like) are exempt from the body rules.**
   That wording is git's.

### What the dash ban reads

8. **The dash ban reads the working tree minus what git ignores.** An unstaged new file, an agent
   writing an ADR or a task file, is the most common way prose enters the repo, so `git ls-files`
   or the index would let the check pass on the document being written and fail only once somebody
   stages it. Skipping what git ignores removes generated and local output (Tauri schemas,
   coverage JSON, measurement samples), whose only remedy would be deleting a file the repo does
   not ship. Git is asked once (`git ls-files --others --ignored --exclude-standard --directory
   -z`), and a wholly ignored directory is skipped rather than descended, which keeps the walk out
   of ignored bind targets filled with GGUFs and dumps. On a clean checkout the set is exactly the
   tracked text files, so the printed count is the same on every machine. **A git that cannot
   reply is exit 2**, so `--root` must name a git working tree, and a walk that read no text file
   fails (`MIN_FILES = 1`). The walk itself and its skip list are shared with the other scans
   ([ADR-0062](ADR-0062-shared-check-readers.md)).

### The commit body

9. **The body wraps at 72 columns (`MAX_BODY_WIDTH`), below a header capped at 72 by its own
   check.** A line past the wrap is exempt when its longest word alone is over it (a URL, a path,
   a long identifier), since no wrapping can fix it.

10. **A paste is declared by what it is: a line inside a code fence, or one whose first token is a
    bare `$` prompt.** `classify_lines` is the one walk that decides which lines are pasted, and
    both rules below use it. Fences are read by the shared reader
    ([ADR-0062](ADR-0062-shared-check-readers.md), decision 6); line 1 is the header and is never a
    paste; a fence marker belongs to its block; and a fence left open is reported at the line that
    opened it, since otherwise one stray fence exempts the rest of the message. The prompt marks
    its own line only, so program output needs a fence. A leading indent is not a paste mark: over
    433 commits every line indented four or more spaces was prose.

11. **A paste is exempt from the wrap, the word count and the dash ban, and from nothing else.**
    All three are about text as typed and their remedies (reflow, cut, restructure) do not exist
    for a paste: moving a newline or dropping `--` from `cargo llvm-cov -- --nocapture` changes
    the command, and all three dash forms are exempt because pasted output can contain an em
    dash. The volatile-reference ban and the resolving-hash check still apply, because they are
    about the message reading correctly after its pointers move, and their remedy survives a
    paste: `git show <sha>` says what a pasted hash meant.

12. **A `BREAKING CHANGE:` footer wraps like the prose it is.** Git does not parse it as a trailer
    (its token has a space), and a Conventional Commits parser reads a footer value across
    newlines to the next token, so wrapping loses nothing, while an exemption keyed on the token
    would exempt a whole paragraph. The rules never require a message this check refuses: the
    footer is required and so is the wrap, and the two together pass.

13. **The volatile-reference ban is deliberately blunt.** It rejects a slice, decision-record,
    assumption, increment, check, decision or audit number, and the word "roadmap" outright, so a
    commit that edits the plan says what it changed rather than naming the file.

14. **The body is at most 50 words (`MAX_BODY_WORDS`), counted over the lines the paste walk left
    as prose.** A body with room for a page of reasoning attracts a page of reasoning, which
    belongs in `docs/`. Words are whitespace-separated tokens on every non-pasted line below the
    header, so a fenced mutation table and a pasted command cost nothing, and the count is
    reported once with its number, because the remedy is to cut the paragraph rather than a line.

## Consequences

- Both rules fail the build rather than degrading silently, and each was shown failing on a real
  violation: an em dash in a doc and in a docstring, and a message citing a slice, a decision
  record and a live hash.
- Prose loses a mark. Restructure the sentence; a comma where an em dash was is usually a worse
  sentence, not a fixed one.
- `commitlint.py` calls `git` but uses only the standard library and passes when git is absent, so
  the hook runs under a plain `python3`.
- A message that needs more than 50 words has to point at a document instead, which is where the
  reasoning was meant to be. A fence exempts its own lines from the count, so the exemption a
  mutation table already had is the one that keeps it.
- A fence around ordinary prose exempts it from the wrap and the dash ban. The exemption is the
  author's declaration, the only marker that does not guess, and nothing distinguishes a paste
  from prose that resembles one. A pasted `git log --oneline` is refused, every line being a hash
  that stops resolving.
- The dash rule cannot be enforced on anything outside this repo's history.

## Alternatives rejected

- **Capping sentences rather than words.** Finding a sentence boundary needs a parser that knows
  abbreviations and version numbers, and three long sentences are exactly what the cap is against.
- **Banning only the spaced en dash.** A plain hyphen is how a range is typed, and one rule is
  simpler than two.
- **Banning `--` in files.** It would abandon the inline-reason form the escape-hatch rule relies
  on.
- **Exempting the checks' own files.** It leaves a hole exactly where the rule is defined.
- **Reading `git ls-files` or the index for the dash ban.** Both miss the unstaged document being
  written.
- **A leading indent as a paste mark.** It would unwrap prose and exempt nothing ever written here.
- **Exempting a paste from every rule.** The volatile-reference and hash rules keep their remedy in
  a paste, so they keep their effect.

## Related

- [AGENTS.md](../../AGENTS.md) (Prose, Commits), [ADR-0040](ADR-0040-prose-and-comment-style.md)
  (the prose rules these checks cover part of).
- [ADR-0062](ADR-0062-shared-check-readers.md) (the walk, git's environment and the fence reader
  the checks share), [ADR-0063](ADR-0063-compose-checks.md) (the compose checks that grew beside
  these), [ADR-0064](ADR-0064-core-public-surface.md) (the core barrel and the line cap).
- The module doc for the repo checks: [repo checks](../modules/repo-gates.md).
