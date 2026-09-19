# Backlog file names use words their titles do not

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Verified:** 2026-09-19

A task file is `NNN-slug.md`, and the slug is written from the title the day the task is opened.
A title can be edited afterwards and the file name cannot follow it, because renaming a file breaks
every link aimed at it.

97 of the 683 refinement task files now have a slug using a word the table in AGENTS.md bans:
`spelled` in 15 of them, `arm` in 10, `carries` in 7, `sweep` in 6, and `gate`, `lever` and
`sitting` in 5 each. No host task file does. A slug is not prose, no check reads it, and both
indexes give the current title beside every link, so this costs a reader only when they look at the
directory listing instead of an index.

**What would close it.** Rename each file and keep its number, which is the task's identity, then
fix every link to it. `just backlog` rewrites the links in both indexes, but a link from a decision
record or from another task file is written by hand. The alternative is a decision that the names
stay, on the ground that the index is how a task is found.

## History

- 2026-09-19: opened after counting the slugs against the table in AGENTS.md.
