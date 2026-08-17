# A red sweep leaves no trace in the repo

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a sweep red that was read late or not at all, or a schedule that stopped firing without anyone noticing, either being the notification having been the only channel.

Opened 2026-08-17 by the pass that put the shuffle sweep on a clock
([R-288](288-nothing-schedules-the-shuffle-sweep.md), [ADR-0002 sweep-schedule
addendum](../../adr/ADR-0002-toolchain-gates.md)). The sweep now runs weekly, and every part of it
this repo owns was proved: the seed is drawn, validated, written to the run summary before the
sweep starts, and the recipe goes red on a planted order dependency naming the test. What was not
proved, because proving it means firing the real thing, is the last hop. GitHub's documented
behaviour is to notify the account whose commit last touched the cron when a scheduled run fails,
so the red's only push channel is an email governed by settings that live outside this repo, and
nothing in the tree records that a sweep ran at all, let alone what seed it drew.

That leaves two failure modes with no in-repo evidence. A red that nobody is notified about sits in
the Actions tab looking exactly like a run nobody has opened yet. And a schedule that stops firing,
which GitHub does to a public repository after 60 days without activity, looks from inside the repo
identical to a schedule that fires and passes: the absence of a red.

**What would close it, and why none of it was taken now.** A failure step that opens an issue is
the obvious shape and the one that turns the red into a durable artifact somebody has to close, at
the cost of widening `permissions` to `issues: write`, of a duplicate-suppression policy so a red
that persists for a month does not file four issues, and of API logic that no local run can
exercise, which is the same untestable hop one layer further in. A status badge makes a red visible
to anyone who opens the README and answers nothing about who looks. A committed record of each
run's seed would make the schedule's silence legible, at the cost of a bot commit on a repo whose
history is deliberately one author's. All three are worth less than the first evidence that a real
red went unread, which is the trigger above; until then the sweep gates nothing, so the cost of
reading it late is bounded by how long the pair it names has already been latent.
