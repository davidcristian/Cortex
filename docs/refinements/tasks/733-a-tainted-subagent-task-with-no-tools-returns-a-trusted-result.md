# A tainted subagent task with no tools returns a trusted result

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-09-25

Decision 1 of [ADR-0013](../../adr/ADR-0013-untrusted-content.md) states that no path under-taints.
A subagent task spawned on a tainted turn has `SubagentTask.tainted` set, and the roster forces the
pick for it, but `SubagentRunner.run` (`cortex_core/runner.py`) sets `SubagentResult.tainted` from
the attempt's own `TaintLedger` alone. That ledger is marked only by an untrusted tool result, so a
subagent with no tools returns `tainted=False` for a tainted task; a script over the runner's test
fakes reads `False`. `SpawnSubagentsTool.invoke` (`cortex_core/spawn.py`) then returns the batch
as `Trust.TRUSTED`, so the reply reaches the cortex without the untrusted wrapper.

The reply can follow the attacker's text. The task's `context`, which the cortex writes and which
can quote untrusted material, goes to that subagent as a system message with no preamble and no
fence (`task_messages` in `cortex_core/subagent_attempt.py`). On that request the pick obeys an
injection in 29 of 75 constrained draws on the CPU
([subagent CPU rows](../../readings/subagent-cpu-rows.md#the-constrained-reply-path)). The cortex's
own turn stays tainted, so the confirmation rule still stops an outbound action on it; what is lost
is the framing of the reply.

**What would close it.** A tainted task's result is tainted whatever its ledger reads, with a
runner test for a subagent with no tools, and ADR-0013 names the rule. Whether the context of a
tainted task also goes fenced, or as a user message, is a framing choice the same rows can
measure, with a variant that changes only the role or the fence.

## History

- 2026-09-25: opened by
  [R-715](715-the-subagent-pick-obeys-framed-injections-as-often-as-the-qwen-candidates.md), whose
  constrained reply path rows send a tainted task's context as a system message.
