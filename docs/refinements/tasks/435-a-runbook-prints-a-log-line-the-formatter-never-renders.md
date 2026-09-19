# A runbook prints a log line in an order the formatter never renders

**Status:** done 2026-08-25
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`docs/runbooks/model-swap.md` prints one failed-handoff line word for word, as the thing to look
for while somebody is waiting. It printed the fields in the order the call site writes them,
`turn_id` then `reason`. The shipped formatter prints them in name order (`render_fields` sorts),
so what a container emits is `reason=... turn_id=...` and always was. The sample had been wrong
since the day the field was renamed onto the turn's name, and nothing reported it, because nothing
compares a documented sample with what the code would render.

The crosscheck registry gets close and stops short: it ties the field names in that sample to their
declarations, so `turn_id` cannot change there. It says nothing about the order they appear in, the
message they follow, or whether the line is one the code could produce at all.

A second instance of the same class, found the same way. Both the swap runbook and
[tools-mcp.md](../../runbooks/tools-mcp.md) tell an operator to run `grep turn_id=t-...`, and no
turn id has ever started with `t-`: `new_turn_id` in
`brain/packages/core/src/cortex_core/conversation.py` returns `str(uuid4())`, and a session id is
`crypto.randomUUID()` from `body/app/src/overlay/useOverlay.ts`. The `t-` and `s-` prefixes are the
test harness's fixture ids (`swap_harness.py` sets `SESSION = "s-handoff"`, `TURN = "t-handoff"`)
and they read in the runbooks as a real prefix to grep for. The registry covers that sentence, so a
check keeps the fiction in place.

Three shapes for a check, none obviously best. Parse fenced lines that look like log records and
re-render them through `PlainFormatter`, which is precise and needs the brain importable from a
scripts-side check that imports nothing today. Render the documented line from real values in the
brain suite and assert the runbook contains it, which is cheap and puts a doc assertion in a code
suite. Or generate the samples instead of writing them, which removes the question and costs a
build step.

## History

- 2026-08-25: opened by the close of
  [R-417](417-the-swap-path-never-names-the-conversation.md), whose edit to that same sample turned
  up the wrong order. Filed against ADR-0046.
- 2026-08-25: closed as ADR-0046 decision 7. Checking again found the headline defect already
  fixed: the swap runbook prints the failed-settle line in name order, corrected by the same close
  that filed this entry. What was live was the prefix fiction and the check question. Both greps in
  both runbooks lost `t-`, each runbook now states that an id is a bare `uuid4` or
  `crypto.randomUUID` where a reader meets the grep, and the two registry search texts that had
  been keeping the fiction in place moved onto the corrected sentences. The check question was
  answered against all three shapes above, in favour of a fourth that costs one line: the
  conversation's search text for that sample is now anchored on the message plus the field that
  sorts in front of it, which fixes the whole three-field order through the scan that already runs.
  Which fields belong on the line stays unchecked and is filed as
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md).
