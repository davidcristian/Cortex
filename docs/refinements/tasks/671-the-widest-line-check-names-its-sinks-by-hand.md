# The widest-line check names its sinks by hand

**Status:** open, fix when it bites
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-15
**Trigger:** a third sink writing a log line whose fields a caller or a model can fill. The sinks
that exist are read off the composition root, `grep -rn "Logging.*Sink" brain/packages/*/src`,
which names both the class and the builder that wires it; a name in that answer with no case in
`brain/packages/orchestrator/tests/test_widest_line.py` is the trigger fired.

Opened 2026-09-15 by the close of
[R-337](337-a-bounded-value-leaves-the-line-unbounded.md), which held the widest line each shipped
sink builds under the log driver's cliff and left the set of sinks a written list.

`test_widest_line.py` has one case per sink and both cases are hand-written: one names
`LoggingAuditSink` and its eleven keys, the other `LoggingRecallSink` and its eleven. A sink that
lands in the brain tomorrow is held by neither, and nothing says so. The same shape is what
`flagcheck.py` refused to accept on the subagent servers, where the set a rule runs over is derived
from the stack's own wiring rather than read from a list, so a server added anywhere is covered the
day it is written (ADR-0029 addendum on deriving the set a rule runs over).

**Why it was left.** Two sinks, both old, and a third is a change somebody is making deliberately
rather than something that appears. The cost of the miss is one unmeasured line rather than a wrong
answer: the check that exists does not become false when a sink is added, it just stops being
complete.

**What would close it.** Derive the sink set the way `flagcheck.py` derives its servers, off the
composition root's own imports rather than off a list here, and fail when a derived sink has no
case. The awkward half is that a case is not mechanical: each one has to know which of that sink's
fields a caller can fill, which is the judgement the whole check turns on and the one thing a
derivation cannot supply. So the derived form is most likely a gate that fails on an unnamed sink
and leaves the naming to a person, which is a smaller thing than it first reads and is probably the
right size.
