# Commit body 72-column wrap check

**Status:** landed 2026-07-19
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-07-18, fix-when-it-bites, by an audit that measured the drift rather than assumed it.
[AGENTS.md](../../../AGENTS.md) states one width rule for a commit message ("the body explains what
and why, wrapped at 72"), and `scripts/commitlint.py` enforces `MAX_HEADER_LENGTH = 72` on the
header alone; nothing looks at the body. Measured over the seven most recent commits at the time:
every one has body lines past 72, the worst at 77, so the drift is endemic to the tree rather
than introduced by any one change, which is exactly what an unenforced rule looks like. It is
cosmetic (`git log` in an 80-column terminal wraps them, it does not truncate) and that is why
it waits. **What would close it:** one more check in the same walker that already reads every
line for dashes and volatile references, plus a decision on the exceptions a hard wrap needs,
which is the whole reason this is not a two-line patch: a URL, a pasted command, a code fence,
or a `BREAKING CHANGE:` footer can all legitimately exceed 72 and must not be reflowed, and a
gate that fails on them would be rewriting messages rather than checking them. **Trigger:** the
first time an over-wide body actually costs something (a message read in a narrow pager or a
release-note extraction that assumes the wrap), or a deliberate reflow pass over the history,
after which the gate is what keeps it reflowed. Until then the rule stands as convention, the
way imperative mood does, and this entry is the record that it is convention rather than gate.

**Landed 2026-07-19, with one of the four exceptions this entry called the actual design
([ADR-0026 wrap addendum](../../adr/ADR-0026-prose-style-gates.md)).** `scripts/commitlint.py` now
measures every line below the header against a new `MAX_BODY_WIDTH = 72`, inside the same walker
that already read each line for dashes and volatile references, exactly as the entry predicted;
the header keeps `check_header`'s own cap so one long subject is one complaint rather than two.
The exception that shipped is `too_wide`: a line past the wrap whose longest word alone exceeds
it has nowhere to break, so a URL, a path, or a long identifier is exempt, while ordinary prose
past the wrap is not. Proven against the four 73-character lines that had already reached master
(flagged with their line numbers and widths) and against the wrapped bodies it must pass. The
drift the entry measured is therefore gated rather than convention, and the trigger it waited
for turned out not to be what moved it: the rule was enforced because a slice's own predecessor
had recorded the same ungated rule as a defect, not because a narrow pager finally cost
something. What the landing did **not** decide is the rest of the exception design, which is the
residual below.

## Trail

- 2026-07-18: Opened as fix-when-it-bites by an audit that measured the drift rather than assuming
  it, taking the area from two entries to three. Every one of the seven most recent commits at
  that moment had body lines past 72, the worst at 77.
- 2026-07-19: Landed. `scripts/commitlint.py` now measures every line below the header against
  `MAX_BODY_WIDTH = 72` inside the walker that already read each line for dashes and volatile
  references, and the area held at three because one entry opened behind it. The index records
  that the same commit changed a gate's behaviour and touched no deferral record at all, the first
  in fifty to do so, which is why three records moved that day rather than one.
