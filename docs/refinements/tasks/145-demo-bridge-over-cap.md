# The demo bridge over the line cap

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

`bridge/demoBridge.ts` was over the line cap and the entry argued for leaving it there. It is the
browser-dev fake, excluded from coverage as the frontend equivalent of the real Tauri bridge and
exercised by hand rather than in CI. Splitting its canned script into a constants module would
have added a second entry to `vite.config.ts`'s coverage `exclude` list, which the entry read as a
bigger concession than a long dev-only fake.

**Split 2026-08-03, along the line the entry named, with two of its numbers corrected.** The 326
it printed was stale the day it was filed: the file had already gone to 351 on 2026-07-20, and
nothing measured it again for fourteen days. "The one overlay source still over
that cap" was true on 2026-07-20 and false from 2026-07-21
([R-144](144-two-overlay-modules-over-cap.md)).

The canned script left for `bridge/demoScript.ts` (141 lines: the reply, the reasoning trace, the
confirm round and its draft, the outage details, and the seeded switcher, reminders and
transcripts), taking the bridge from 351 to 234 with only behaviour left in the class.
`sessions()` and `reminders()` are functions rather than constants, so each `DemoBridge` still
stamps its seed relative to its own construction.

The cost was measured rather than assumed: leaving `demoScript.ts` out of the coverage `exclude`
list reports it 0% over lines 8 to 141 and takes the overlay from 100% to 97.45%, exit 1, so an
exclusion was required. But it is not a new kind of unmeasured file, since the demo bridge had been
excluded since it was written; it is the same exclusion written across the two files it now
occupies. It is an explicit path rather than a `demo*.ts` glob, because loose enumeration in check
config has already cost this repo once ([repo-checks.md](../index.md#repo-checks), the fail-open
`scripts/` config fixed 2026-07-12).

**The entry's own trigger fired on 2026-08-11, and the exclusion came off with it.** The demo
bridge is now driven as an implementation of a port with a shared check list, the same thirteen
checks in `body/app/src/bridge/bridgeContract.ts` the fake is held to, with its own suite beside
it for the recorded conversation and the four prompts that trip a hook. Both files left the
coverage `exclude`, and the 0% measured before was a fact about a script nothing imported in CI
rather than a property of the file: with the bridge under test every line of the script is reached,
the transcript lookup's two branches included. What is left in that list is `main.tsx` and
`tauriBridge.ts`, under [ADR-0068](../../adr/ADR-0068-port-contract-lists.md) decision 7.

## History

- 2026-07-20: Filed at 326 lines and staying, with the trigger set at the demo growing a second
  behaviour worth testing.
- 2026-08-03: Split along exactly the line it named, against a corrected cost and two corrected
  numbers.
- 2026-08-11: The trigger it set fired, and both files left the coverage `exclude`.
