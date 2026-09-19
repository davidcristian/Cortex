# A figure that describes only this machine is caught by eye

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** a power, clock, temperature or fan reading stands as an absolute in a tracked text
file on a line other than the five named as standing in the 2026-09-19 trail bullet, or a document
tells an operator to take a card reading and gives a value where it should give the fields to
query. The search is `git grep` for a number followed by W, watts, MHz, GHz, °C, a bare C or MT/s.
**Verified:** 2026-09-19

Opened 2026-09-14 by the sweep of 2026-09-13 that put the measurement rule in the Prose section of
[AGENTS.md](../../../AGENTS.md) and its convention in the
[ADR-0029 ratio addendum](../../adr/ADR-0029-vision-screen-capture.md). A figure that describes
only the machine it was read from is written as a ratio of that machine's own numbers; where an
operator takes the reading, the fields they query are named instead of a value; and a figure a
reader compares directly against their own hardware, the 24 GB VRAM budget above all, stays
absolute. The corpus was brought under that rule by hand the same day, and nothing in `just check`
reads a figure, so the rule holds only as long as each reader applies it. This is the second
written record of a rule checked by eye, beside
[R-631](631-the-purpose-paragraph-describes-the-scans-by-eye.md), and the two are not the same
case: there a module already reads the real set and the eye only compares two lists, where here
nothing mechanical reads the corpus at all.

**Where the line falls.** The rule does not ban figures, so no scan can run on "a number with a
unit". Three classes sit behind that sentence, and only the first is decidable by a scan on its
own.

- **Units with no cross-machine reading**: watts, an SM clock in MHz or GHz, a temperature, a fan
  speed, a memory transfer rate. Nothing in this repo compares its own hardware against a wattage
  to decide whether something fits, so a figure in one of these units is a violation by its unit,
  and a scan needs no judgment to say so.
- **Units this repo spends on both kinds of figure**: a memory size, a duration, a token rate.
  These are undecidable from the number. The 24 GB VRAM total is the comparison
  [ADR-0001](../../adr/ADR-0001-architecture.md) and the engineering contract are built on, and the
  1867 to 1932 MiB an idle card reads, which the runbook subtracts to get its weights column, is a
  property of this card; both are memory sizes. The runbook's `about 30 tokens a second` stands in
  the same sentence as two ratios and the sweep left it there. What separates a keeper from a
  violation in this class is what the sentence is for, which is a reader's judgment.
- **The ratio's own standing**: whether "about a third of its full power" divides this card's own
  numbers, and whether the figures it divides were read in the same sitting. Nothing outside the
  prose says, so no scan reaches it. One narrow piece of the second half is mechanical: a line that
  names an `nvidia-smi` field and also carries a bare figure is an instruction publishing a value
  where it should publish a query.

**What a false positive costs an author.** Run the narrow design over the tree on 2026-09-14 and it
returned one line: the README's `5600 MT/s`, inside the sentence that names the development laptop
on purpose and that the rule keeps. (Two temperatures written with a bare C were missed by that
search; the 2026-09-19 trail bullet names them.) So the gate needs a declared exemption before it
passes once, and the idiom for that already exists, `dashcheck.py`'s `dashcheck: allow` pragma with
a reason on the line. That one exemption is also the whole shape of the risk. An author who writes a
correct sentence gets a failure, and their two remedies are a pragma that nobody re-reads afterwards
or dropping a true fact. A wide design makes that the normal outcome rather than the rare one: a
figure with a unit appears on 2671 lines of 251 markdown files, nearly all of them weights, context
sizes, durations and VRAM totals that stay, so the allowlist would become a second copy of the
measurement corpus and a failure would stop carrying information.

**What it would have caught.** The narrow search over the commit before the sweep returns seven
lines in three files. Six carry the eight wattage figures the sweep rewrote: the README's hardware
sentence, the introduction and the load column heading of both 2026-06-29 load-time tables, and the
runbook's note that its later uncapped rows are not comparable with the capped ones. The seventh is
the README line that stayed. The sweep changed no figure the unit search would have missed, so on
the one corpus anybody has swept, that design found everything and was right about six of its seven
reports. Two things the measurement does not say. The sweep is one reading by one reader, and the
design is being scored against the reading that produced it. And those figures were legal until the
day the rule landed, so the stretch from 2026-06-28 and 2026-06-29, when the README sentence and
the two tables were written, to 2026-09-13 is not a miss by anybody.

**What would close it.** The decision is the maintainer's, and this entry is a proposal rather than
a plan: a thirteenth cross-tree scan is an addition to the set the contract, the workflow comment
and the documentation index all name, so it costs a module and its tests at full coverage, a
`check-*` recipe, a step in CI's `cross-tree` job, those three rosters and the repo-gates module
doc. What it buys is a guard against the next wattage, and one has already been written since the
rule landed (the 2026-09-19 trail bullet). Until the maintainer decides, this stays the record that
one prose rule is applied by readers and checked by nobody, which is what the origin addendum of
2026-09-14 says it is.

## Trail

- 2026-09-14: opened by the sweep that landed the measurement rule and rewrote the figures
  predating it. Measured on the day: the narrow search returns seven lines in three files before
  the sweep and one after it, and a unit-blind search returns 2671 lines in 251 files. Not fired,
  the one standing line being the README sentence the rule keeps. Recorded in the ADR-0029
  addendum of the same day on what a scan over this rule could and could not decide.
- 2026-09-19: **the trigger fired, and the reading of 2026-09-14 was short by two lines.** The
  unattended-sitting addendum of 2026-09-17 in ADR-0029 published the launcher's between-row card
  readings as absolutes, a clock in MHz of the card's maximum and an enforced ceiling in watts of
  `power.max_limit`, three days after the rule landed. The launcher of each sitting, a script under
  the ignored `measurements/` directory, prints its `host card` lines in those units, and the
  addendum copied them; the harness's own `card reading` lines print ratios and were published
  correctly beside them. That sentence is rewritten in this change as ratios of the same readings,
  taken from `measurements/sitting-2026-09-17/run.log` on the host: clock 0.59 to 0.61 of
  `clocks.max.sm`, ceiling 0.80 to 0.87 of `power.max_limit`. Separately, the search this entry
  described found the README line alone because it looked for °C, and two temperatures from the
  2026-09-13 sittings are written with a bare C, in the ADR-0029 addendum on the software-capped
  dialog sitting and in the one on the card's idle reading. Both stand for now. The ratio rule gives a temperature no form unless the card's own threshold is read beside
  it, neither sitting read one, and replacing either with a field name would drop the only record
  of the reading. With the degree-less spelling in the search, it returns five lines and this
  entry names all five as standing: the README's hardware sentence, the two quotations of its
  memory transfer rate (in the 2026-09-14 ADR-0029 addendum and in this file's paragraph on what a
  false positive costs), and those two temperatures. Neither this bullet nor the addendum recording
  it repeats a figure, so neither adds a line to the search.
  The proposal is unchanged and still the maintainer's: a scan now has one caught regression to
  show for itself, which was not true when it was written, and its unit set must carry the bare C.
  Recorded in the ADR-0029 addendum of the same day.
