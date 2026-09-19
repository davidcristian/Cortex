# A figure that describes only this machine is caught by eye

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Trigger:** a power, clock, temperature or fan reading stands as an absolute in a tracked text file
on a line other than the five named as remaining in the 2026-09-19 history entry, or a document
tells an operator to take a card reading and gives a value where it should give the fields to
query. The search is `git grep` for a number followed by W, watts, MHz, GHz, °C, a bare C or MT/s.
**Verified:** 2026-09-19

The measurement rule in the Prose section of [AGENTS.md](../../../AGENTS.md) says that a figure
describing only the machine it was read from is written as a ratio of that machine's own numbers;
that where an operator takes the reading, the fields they query are named instead of a value; and
that a figure a reader compares directly against their own hardware, the 24 GB VRAM budget above
all, stays absolute. The corpus was brought under that rule by hand, and nothing in `just check`
reads a figure, so the rule holds only as long as each reader applies it.

**Why no scan is obvious.** The rule does not ban figures, so nothing can run on "a number with a
unit". Three classes sit behind that sentence and only the first is decidable by a scan.

- **Units with no cross-machine reading**: watts, an SM clock in MHz or GHz, a temperature, a fan
  speed, a memory transfer rate. Nothing here compares its own hardware against a wattage to decide
  whether something fits, so a figure in one of these units is a violation by its unit alone.
- **Units this repo uses for both kinds of figure**: a memory size, a duration, a token rate. The
  24 GB VRAM total is the comparison [ADR-0001](../../adr/ADR-0001-architecture.md) and the
  engineering contract are built on, and the 1867 to 1932 MiB an idle card reads, which the runbook
  subtracts to get its weights column, is a property of this card; both are memory sizes. What
  separates a keeper from a violation here is what the sentence is for.
- **The ratio itself**: whether "about a third of its full power" divides this card's own numbers,
  and whether the figures it divides were read in one run. Nothing outside the prose says. One
  narrow piece is mechanical: a line that names an `nvidia-smi` field and also has a bare figure is
  an instruction publishing a value where it should publish a query.

**What a false positive costs an author.** Run over the tree on 2026-09-14, the narrow search
returned one line: the README's `5600 MT/s`, inside the sentence that names the development laptop
on purpose and that the rule keeps. (Two temperatures written with a bare C were missed by that
search; the 2026-09-19 history entry names them.) So a check needs a declared exemption before it
passes once, and the idiom exists, `dashcheck.py`'s `dashcheck: allow` pragma with a reason on the
line. A wide design makes that the normal outcome rather than the rare one: a figure with a unit
appears on 2671 lines of 251 markdown files, nearly all of them weights, context sizes, durations
and VRAM totals that stay, so the allowlist would become a second copy of the measurement corpus.

**What it would have caught.** The narrow search over the commit before the rule returns seven
lines in three files. Six have the eight wattage figures that were rewritten: the README's hardware
sentence, the introduction and the load column heading of both 2026-06-29 load-time tables, and the
runbook's note that its later uncapped rows are not comparable with the capped ones. The seventh is
the README line that stayed. No figure was changed that the unit search would have missed. Two
caveats: that pass is one reading by one reader, and the design is being scored against the reading
that produced it; and those figures were legal until the rule was added, so the stretch from
2026-06-28 and 2026-06-29 to 2026-09-13 is not a miss by anybody.

**What would close it.** The decision is the maintainer's, and this entry is a proposal. A
thirteenth cross-tree scan is an addition to the set the contract, the workflow comment and the
documentation index all name, so it costs a module and its tests at full coverage, a `check-*`
recipe, a step in CI's `cross-tree` job, those three rosters and the repo checks module doc. What it
buys is a guard against the next wattage, and one has already been written since the rule was added.

## History

- 2026-09-14: opened by the pass that added the measurement rule and rewrote the figures predating
  it. Measured that day: the narrow search returns seven lines in three files before the pass and
  one after it, and a unit-blind search returns 2671 lines in 251 files. Not fired, the one
  remaining line being the README sentence the rule keeps. Recorded in the ADR-0029 record of the
  same day on what a scan over this rule could and could not decide.
- 2026-09-19: **the trigger fired, and the 2026-09-14 reading was short by two lines.** The record
  of the 2026-09-17 unattended run published the launcher's between-row card readings as absolutes,
  a clock in MHz of the card's maximum and an enforced ceiling in watts of `power.max_limit`, three
  days after the rule was added. Each run's launcher, a script under the ignored `measurements/`
  directory, prints its `host card` lines in those units, and the record copied them; the harness's
  own `card reading` lines print ratios and were published correctly beside them. That sentence is
  rewritten here as ratios of the same readings, taken from
  `measurements/sitting-2026-09-17/run.log` on the host: clock 0.59 to 0.61 of `clocks.max.sm`,
  ceiling 0.80 to 0.87 of `power.max_limit`. Separately, the search found the README line alone
  because it looked for °C, and two temperatures from the 2026-09-13 runs are written with a bare
  C, in the records of the software-capped dialog run and of the card's idle reading. Both stay for
  now: the ratio rule gives a temperature no form unless the card's own threshold is read beside it,
  neither run read one, and replacing either with a field name would drop the only record of the
  reading. With the degree-less form in the search it returns five lines, and this entry names all
  five as remaining: the README's hardware sentence, the two quotations of its memory transfer rate
  (in the 2026-09-14 record and in this file's paragraph on false positives), and those two
  temperatures. The proposal is unchanged and still the maintainer's: a scan now has one caught
  regression to show for itself, and its unit set must include the bare C. Recorded in
  [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) rule 10.
