# A documented log sample can still print the wrong fields

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-25 by the close of
[R-435](435-a-runbook-prints-a-log-line-the-formatter-never-renders.md), which pinned the order of
the one verbatim log sample this repo prints and left its membership unpinned.

`docs/runbooks/model-swap.md` prints the failed-settle line verbatim, and
`scripts/logcouplings.py` now anchors the conversation's needle on the message plus the field that
sorts in front of it, so the three fields cannot be rearranged without the constant scan noticing.
What the anchor says nothing about is which fields belong on the line. If `swap_settle.fail`
stopped attaching `reason`, the sample would go on printing it and the scan would go on agreeing,
because every needle it holds would still be found. If the call site started attaching a field
that sorts after `session_id`, say `state` or `task_id`, the sample would be missing it and
nothing would say so. Only a field that sorts into the anchored gap, between the message and
`session_id`, is caught, and that is an accident of the alphabet rather than a property.

The same is true, more completely, of the two samples that are pinned by nothing: the audit
transcript in [ADR-0009](../../adr/ADR-0009-tools-mcp.md) and the redaction sample in
[ADR-0038](../../adr/ADR-0038-ranked-recall.md). Those are evidence of a live run rather than
instructions to an operator, which is the argument for leaving them, and it is a weaker argument
than it sounds: a reader who copies a field list out of a recorded transcript is reading it as a
statement about what the code emits.

**Why it was left.** The close it came out of argued its way out of all three gate shapes the
original entry offered, and the anchor it built instead is free. Membership is not free: it needs
the set of keys one `extra=` attaches to be readable from outside the module, which is either an
import the scripts side does not have or a parse of the call site the scan would have to grow.
The three shapes are still the three shapes, and the argument against each is written down in the
ADR-0009 bare-id addendum, so this entry is the place to reopen it if a second verbatim sample
ever appears and makes the bill worth paying.

**What would close it.** Either a way for a needle to say "these fields and no others follow this
message", which means teaching the scan to read a call site's `extra=` keys, or a written argument
that one sample with its order held is a small enough exposure to leave, with the audit
transcripts explicitly declared evidence rather than contract.

## Trail

- 2026-08-25: opened by the close of
  [R-435](435-a-runbook-prints-a-log-line-the-formatter-never-renders.md). Recorded under what the
  ADR-0009 bare-id addendum defers.
