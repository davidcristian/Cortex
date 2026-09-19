# The dash ban reads a working tree rather than a commit, and now says so

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-checks.md)

Measured on a clean working tree on 2026-08-24: the scan reads 1252 text files, git tracks 1268
paths, and the two sets are not nested. Ten files it reads are untracked, all of them build output
or local scratch that a `.gitignore` covers: the five generated schemas under
`body/app/src-tauri/gen/`, `body/coverage.json`, three `measurements/*.json` blocks and
`sandbox/hello.txt`. Twenty six files git tracks it never reads, all of them binary assets it is
right to skip.

Two consequences. A banned dash inside generated or ignored output fails the check, and the remedy
is to delete a file the repo does not ship rather than to rewrite a sentence. And the printed count
is a fact about one machine's working tree rather than about the commit, so the same commit reads a
different number in CI.

The question is what the dash ban's collection actually is. The candidates are the working tree
(the answer at the time, which catches a dash in an untracked file before it is committed), the
index, and `git ls-files` (what the repo ships, which would make the printed count reproducible).

## History

- 2026-08-24: filed by the close of
  [R-409](409-a-gates-success-line-names-no-collection.md), which made the dash ban print how many
  text files it read and made the difference between that number and the repo visible.
- 2026-08-24: closed. The Origin line was wrong and is corrected: it named the constant-scan
  decision record, and this file's own prose already said the rule belongs to the dash ban's own
  record, which is where the decision went. Checked again first and the numbers had moved: 1262
  text files read against 1278 tracked paths, where this file recorded 1252 and 1268, with the same
  ten untracked files read and the same twenty six binary assets tracked and skipped. The
  collection stays the working tree, minus what git ignores. `git ls-files` lost on the case that
  made the walk a walk: an agent writes an ADR, and under `ls-files` the check passes over the
  document being written in front of it and fails only once somebody stages it, the index being the
  same argument one step later. Git is asked once for the paths it ignores, costing milliseconds,
  and a wholly ignored directory is skipped rather than descended, which also stops the walk
  reading GGUFs out of an ignored bind target to decide they are binary. A git that cannot answer
  is exit 2, the same stance the compose bind check takes toward the same dependency, so `--root`
  must now name a git working tree. The walk now reads 1252 files over 234483 lines, 10 files and
  8056 lines less, and on a clean tree that is exactly the tracked text, 1278 paths minus 26
  binaries. The minimum still means what it meant and now has a second way to reach it, a root git
  ignores entirely, covered by its own test. Five planted mutations over the scripts suite. Two
  residues filed: the environment strip that makes a git call inside a hook accurate is written out
  in three modules ([R-419](419-the-git-call-inside-a-hook-is-written-three-times.md)), and
  `SKIPPED_DIRS` restates what `.gitignore` covers for all but one entry
  ([R-420](420-the-skipped-dirs-list-restates-what-git-ignores.md)).
