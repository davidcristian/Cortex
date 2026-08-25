# A runbook prints a log line in an order the formatter never renders

**Status:** landed 2026-08-25
**Area:** repo-gates
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-25 by the close of
[R-417](417-the-swap-path-never-names-the-conversation.md), which had to edit the one such sample
and found it wrong before it changed it.

`docs/runbooks/model-swap.md` prints one failed-handoff line verbatim, as the thing to look for
while somebody is waiting. Until today it printed the fields in the order the call site writes
them, `turn_id` then `reason`. The shipped formatter prints them in **name** order
(`render_fields` sorts, ADR-0038 rendered-fields addendum), so what a container really emits is
`reason=... turn_id=...` and always was. The sample had been wrong since the day the field was
renamed onto the turn's name, and nothing noticed, because nothing compares a documented sample
against what the code would render.

The crosscheck registry gets close and stops short: it ties the field *names* in that sample to
their declarations, so `turn_id` cannot drift there. It says nothing about the order they appear
in, the message they follow, or whether the line is one the code could produce at all. A sample
carrying a field the code stopped attaching, or missing one it started attaching, is invisible the
same way.

The exposure is small but it is the kind that costs at the worst moment: an operator eyeballing a
stream for a shape the runbook drew, and finding the shape is not the one on screen.

**A second instance of the same class, found the same way and deliberately left.** Both the swap
runbook and [tools-mcp.md](../../runbooks/tools-mcp.md) tell an operator to run
`grep turn_id=t-...`, and no turn id has ever started with `t-`: `new_turn_id` in
`brain/packages/core/src/cortex_core/conversation.py` returns `str(uuid4())`, and a session id is
`crypto.randomUUID()` from `body/app/src/overlay/useOverlay.ts`. The `t-` and `s-` prefixes are the
test harness's fixture ids (`swap_harness.py` sets `SESSION = "s-handoff"`, `TURN = "t-handoff"`)
and they read in the runbooks as a real prefix to grep for. The registry pins that sentence, so the
fiction is held in place by a gate. It was left because it spans two runbooks, two registry needles
and possibly other docs, and it wants one deliberate pass rather than a drive-by; the sentence
R-417 added writes `grep session_id=` with no prefix rather than adding a third instance.

**Why it was left.** The close it came out of was about which fields the swap path attaches, and
it fixed the one sample it touched by hand. Making the class impossible is a different piece of
work with at least three shapes and no obvious winner. A gate could parse fenced lines that look
like log records and re-render them through `PlainFormatter`, which is precise and needs the
brain importable from a scripts-side gate that currently imports nothing. A test in the brain
suite could render the documented line from real values and assert the runbook contains it, which
is cheap and puts a doc assertion in a code suite. Or the samples could stop being verbatim and
start being generated, which removes the question and costs a build step.

**What would close it.** Pick one and argue it against the others, or argue the class is not worth
a gate and that the two live samples (this one, and the audit lines ADR-0009 prints) are few
enough to re-derive by hand whenever a field moves. If it is the gate, note that only one runbook
sample and two ADR samples exist today, so whatever is built will be watching a very small set,
and that `logcouplings.py` already knows which files quote these lines.

## Trail

- 2026-08-25: opened by the close of
  [R-417](417-the-swap-path-never-names-the-conversation.md), whose edit to that same sample is
  what turned up the wrong order. Recorded under what the ADR-0009 named-conversation addendum
  defers.
- 2026-08-25: landed as the ADR-0009 bare-id addendum. Re-derivation found the headline defect
  already closed: the swap runbook prints the failed-settle line in name order at HEAD, corrected
  by the same close that filed this entry. What was live was the prefix fiction and the gate
  question. Both greps in both runbooks lost `t-`, each runbook now states that an id is a bare
  `uuid4` or `crypto.randomUUID` where a reader meets the grep, and the two registry needles that
  had been holding the fiction in place moved onto the corrected sentences. The gate question was
  answered against all three shapes the entry offered, in favour of a fourth that costs one line:
  the conversation's needle for that sample is now anchored on the message plus the field that
  sorts in front of it, which pins the whole three-field order through the scan that already runs.
  Membership stays unpinned and is filed as
  [R-438](438-a-documented-log-sample-can-still-print-the-wrong-fields.md).
