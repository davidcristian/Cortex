# The demo bridge over the line cap

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

**`bridge/demoBridge.ts` (326) is the one overlay source still over that cap, and staying.**
It is the browser-dev fake, coverage-excluded as the frontend analog of the real Tauri bridge and
exercised by hand rather than in CI. The obvious split is its canned script (the reply, the
reasoning trace, the gated draft, the outage details) into a constants module, and that module
would be 0% covered the moment it existed, since no test imports the demo bridge. So the split
costs a new entry in `vite.config.ts`'s coverage `exclude` list, and widening that list is a
bigger concession than a long dev-only fake. The trigger is the demo growing a second behaviour
worth testing, at which point the script becomes real data with a real test and the exclusion
question answers itself.

**Struck 2026-08-03, along exactly the seam this entry named, with two of its own numbers
corrected.** The 326 was stale the day it was filed: `42be4c49` had already taken the file to
**351** on 2026-07-20, and nothing measured it again for fourteen days. "The one overlay source
still over that cap" was true on 2026-07-20 and false from 2026-07-21, per the correction above.
What the entry got right is the seam. The canned script left for `bridge/demoScript.ts` (141: the
reply, the reasoning trace, the confirm round and its draft, the outage details, and the seeded
switcher, reminders and transcripts), taking the bridge from 351 to 234 with only behaviour left
in the class, and `sessions()`/`reminders()` are functions rather than constants so each
`DemoBridge` still stamps its seed relative to its own construction. What it got wrong is the
cost, because it weighed the split against a cap nothing enforced. **Measured rather than
assumed:** leaving `demoScript.ts` out of the coverage `exclude` list reports it 0% over lines 8
to 141 and takes the overlay from 100% to 97.45%, exit 1, so the entry was right that an
exclusion is required. But the concession is not a new kind of unmeasured file, since the demo
bridge has been coverage-excluded since it was written; it is the same exclusion spelled over the
two files it now occupies. It is written as an explicit path rather than a `demo*.ts` glob,
because loose enumeration in gate config has already cost this repo once ([repo-gates.md](../index.md#repo-gates),
the fail-open `scripts/` config closed 2026-07-12). The trigger the entry set, the demo growing a
second behaviour worth testing, is untouched and is still what would turn the script into tested
data.

**That last trigger fired on 2026-08-11, and the exclusion it argued for came off with it.** The
demo bridge is now driven as an implementation of a port that has a shared check list, the same
thirteen checks in `body/app/src/bridge/bridgeContract.ts` the fake is held to, with its own
suite beside it for the recorded conversation and the four prompts that trip a hook. Both files
left the coverage `exclude`, and the 0% measured above turns out to have been a fact about a
script nothing imported in CI rather than a property of the file: with the bridge under test
every line of the script is reached by the turns the suites drive, the transcript lookup's two
branches included. What is left in that list is `main.tsx` and `tauriBridge.ts`, and the account
of what the shared list found is the [ADR-0001](../../adr/ADR-0001-architecture.md) addendum of
that date.

## Trail

- 2026-07-20: Filed at 326 lines and staying, with the trigger set at the demo growing a second
  behaviour worth testing.
- 2026-08-03: Struck along exactly the seam it named, against a corrected cost and two corrected
  numbers: the file already stood at 351 the day the entry was filed and still did fourteen days
  later. The exclusion was measured rather than assumed, an unexcluded `demoScript.ts` reporting 0%
  and taking the overlay from 100% to 97.45%, exit 1, but the concession is one explicit path
  extending an exclusion that already existed rather than a new kind of unmeasured file.
- 2026-08-11: The trigger it set fired. The demo bridge is now driven as an implementation of a port
  with a shared check list, both files left the coverage `exclude`, and every line of the script is
  reached by the turns those suites drive, so the 0% measured before was a fact about a script
  nothing imported in CI rather than a property of the file.
