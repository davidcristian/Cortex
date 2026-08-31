# What a bounded trace costs a hard answer is unmeasured

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a deployment moving `CORTEX_REASONING_BUDGET` off its default, or a wrong answer
somebody blames on it.

Opened 2026-08-17 by the trace-budget landing
([ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) trace-budget addendum), which priced the knob in
seconds and left its cost in answers open.

Every number behind that knob is a latency: the trace falls from 2323 to 2996 characters to about
500 at a budget of 128, and the first word from 10.1 to 12.6 s to 1.7 to 2.6 s, with the reply the
same size and still finishing on its own. The quality side has one weak reading and one absence.
The weak reading is four multi-step items with a single right answer (a bat and ball, the five
machines, a train timetable sum, an ages puzzle), each answered correctly at unbounded, at 128 and
with thinking off entirely, which says only that the cortex pick does not need its trace for those.
The absence is everything the trace is actually for: the questions the deep tier was chosen over
faster candidates to reach an answer on ([ADR-0004](../../adr/ADR-0004-model-lineup.md)).

What would close it is a graded arm rather than a timed one: a set of questions hard enough that the
shipped model gets some of them wrong, run across unbounded, a few positive budgets and zero, scored
by something better than a reading of the replies. That is a corpus and a judge, which is why it did
not ride the landing; the landing's own advice, to start at 512 on a tier a user reads and treat
anything lower as a trade, is the placeholder until this exists.
