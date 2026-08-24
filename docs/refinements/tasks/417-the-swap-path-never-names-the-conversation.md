# The swap path never names the conversation, so a chat's evidence stops at the handoff

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-24 by the close of
[R-415](415-the-swap-path-names-its-work-with-bare-nouns.md), which put all eleven of the swap
path's log records onto the turn's own name and found, while reading each one, that not one of them
names the conversation the turn belongs to.

Seven other modules attach `session_id` to a line and the tool audit sink writes it on every call
it records, and the memory runbook tells an operator to grep it. The swap path attaches none: the
conductor's four refusals, the settler's three, boot recovery's stranded record and the deep
phase's two cadence spellings all name the turn and stop there. So `grep session_id=s-...` returns
a chat's recalls, its rank fallbacks, its mid-turn failures, its summaries and every tool call it
made, and returns nothing at all about the handoff that chat asked for, which is the most expensive
thing that happens in it. The turn id joins the two halves only if the reader already has it, and
the reader grepping by conversation is exactly the reader who does not.

The conversation is already in scope at six of the eleven, which is what makes those six cheap:
`run_handoff` and `_prepare` are both handed `session_id`, and the settler's `fail` and boot
recovery each hold a record carrying `HandoffRecord.session_id`. The other five would need it
plumbed, the settler's `_write_state` and `_release_claim` and the deep phase's `_report_cadence`
each taking a bare id rather than the record, so the question there is whether to pass the record
down or to leave those lines naming the turn alone.

**Why it was left.** The close it came out of was about one identity being spelled two ways, which
is a defect a grep already fails on. This is the opposite shape: no line is wrong, and every line
is missing a field. Adding one is a change to what eleven records carry rather than to what they
call it, and the cadence lines in particular already carry seven fields, eight on a spill, so
it wants its own argument about whether a conversation belongs on a line about a tier's throughput.

**What would close it.** Decide per line rather than per module, since the two questions differ: a
refusal and a settle are about a turn somebody is waiting on, and the deep tier's decode rate is
about the machine. Then either attach `session_id` where it was decided, extending
`scripts/logcouplings.py`'s conversation entry with the modules that gained it, or write down that
the swap path deliberately names only the turn and why, where a reader of those lines will find it.

## Trail

- 2026-08-24: opened by the close of
  [R-415](415-the-swap-path-names-its-work-with-bare-nouns.md), whose per record read of the whole
  swap path is what surfaced the missing field. Recorded under what the ADR-0009 sixth-name
  addendum defers.
