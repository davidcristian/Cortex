# The dash ban reads a working tree rather than a commit, and now says so out loud

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-409](409-a-gates-success-line-names-no-collection.md), which made `dashcheck.py` print how many
text files it read and made the difference between that number and the repo visible for the first
time.

Measured on a clean working tree the same day: the scan reads **1252** text files, git tracks
**1268** paths, and the two sets are not nested. Ten files it reads are files git does not track,
all of them build output or local scratch that a `.gitignore` covers: the five generated schemas
under `body/app/src-tauri/gen/`, `body/coverage.json`, three `measurements/*.json` blocks and
`sandbox/hello.txt`. Twenty six files git tracks it never reads, all of them binary assets it is
right to skip.

Two consequences, and only the first is new. A banned dash inside generated or ignored output
fails the gate, and the remedy for it is not to rewrite a sentence but to delete a file the repo
does not ship. And the printed count is a fact about one machine's working tree rather than about
the commit, so the same commit reads a different number in CI, which makes it useless as anything
but a sanity check of the run in front of you. The count is a reading and nothing asserts it, so
neither consequence is a broken gate; the second is a caveat on how far the new number can be
trusted, and the first is a latent red nobody has hit yet.

**Why it was left.** The close was about giving four gates a collection to name, and it named this
one honestly. Changing which files the dash ban reads is a change to the rule, argued at ADR-0026
rather than smuggled in beside a print statement.

**What would close it.** Decide what the dash ban's collection actually is. The candidates are the
working tree (today's answer, which catches a dash in an untracked file before it is committed and
is the reason the walk is a walk), the index, and `git ls-files` (what the repo ships, which is
what the rule is about and which would make the printed count reproducible). Weigh the case that
made the walk right in the first place: a file staged but not committed, and a file written by an
agent mid-session, are both prose this repo is about to own. If the answer stays "the working
tree", then the fix is smaller and is to skip what git ignores, which removes the generated
schemas and the local measurement blocks without touching a file a person wrote.
