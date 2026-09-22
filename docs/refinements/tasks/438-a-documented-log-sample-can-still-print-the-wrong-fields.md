# A documented log sample can still print the wrong fields

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`docs/runbooks/model-swap.md` prints the failed-settle line word for word, and
`scripts/logcouplings.py` anchors the conversation's search text on the message plus the field that
sorts in front of it, so the three fields cannot be rearranged without the constant scan failing.
The anchor says nothing about which fields belong on the line. If `swap_settle.fail` stopped
attaching `reason`, the sample would go on printing it and the scan would go on agreeing, because
every search text it has would still be found. If the call site started attaching a field that
sorts after `session_id`, say `state` or `task_id`, the sample would be missing it and nothing
would say so. Only a field that sorts into the anchored gap is caught, which is an accident of the
alphabet.

The same is true, more completely, of the two samples nothing covers: the audit transcript in
[ADR-0009](../../adr/ADR-0009-tools-mcp.md) and the redaction sample in
[ADR-0038](../../adr/ADR-0038-ranked-recall.md). Those are evidence of a live run rather than
instructions to an operator, which is the argument for leaving them, and it is weaker than it
sounds: a reader who copies a field list out of a recorded transcript is reading it as a statement
about what the code emits.

Checking membership is not free: it needs the set of keys one `extra=` attaches to be readable from
outside the module, which is either an import the scripts side does not have or a parse of the call
site the scan would have to grow.

## History

- 2026-08-25: opened by the close of
  [R-435](435-a-runbook-prints-a-log-line-the-formatter-never-renders.md), which fixed the order of
  the one word-for-word log sample this repo prints and left its membership unchecked. Filed
  against ADR-0046.
- 2026-08-26: closed as ADR-0045, which built a scan of its own, `scripts/samplecheck.py`, with
  `scripts/logsamples.py` reading what a page claims and `scripts/logcalls.py` reading what the
  call attaches. Checking again confirmed the defect exactly as filed and corrected the entry's
  premise about its size: a search for a rendered line returns three samples in `docs/runbooks/`,
  not one. The failed settle, the brain server's boot line in the WSL runbook, and the quarantine
  pair in the scheduling runbook are all instructions to an operator, so the bill this entry priced
  against one sample was being paid for three. The scan compares the level, the logger, the message
  and the field list, as a sequence, which says everything a set comparison would and covers the
  order besides. It compares field names and never values, which keeps it compatible with the
  constant registry's decision that the WSL runbook's captured port is a dated reading rather than
  a coupling. Samples are found rather than registered, so a fourth is covered the day it is
  written. The two ADR transcripts this entry named are declared evidence rather than contract in
  writing, which is the entry's own second option taken deliberately: a dated transcript compared
  with today's code would have to be edited to keep passing. What the close opened is filed as
  [R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md), the coverage question this
  one leaves untouched, and
  [R-445](445-three-checks-each-define-the-markdown-fence-for-themselves.md), the third copy of the
  markdown fence this work added.
