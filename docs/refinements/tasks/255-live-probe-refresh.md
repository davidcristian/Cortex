# A live-probe refresh

**Status:** landed 2026-08-06
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The `/props` vision probe ran **once at startup**. A `llama-server`
restarted without `--mmproj` mid-session left `capture_screen` advertised, so a capture would
be taken, the user notified, and the turn tainted for an image the model cannot read: the full
privacy cost for zero benefit. Re-probing per turn would make the inference adapter stateful,
which is why it was not done; the cheap version is re-probing when a swap changes residency,
since that is the only thing in the system that restarts a model server.

**Closed 2026-08-06, and the entry's premise held while its proposed fix did not** ([ADR-0029
live-probe addendum](../../adr/ADR-0029-vision-screen-capture.md)). The failure was reproduced end
to end against the real stack before anything was built: a `model-host` recreated without
`CORTEX_MMPROJ_FILE_CORTEX` flipped `/props` from `vision: true` to `vision: false` under a brain
whose container never restarted and whose log still held exactly one probe line, and the next "look
at my screen" read the screen, fired the capture receipt, tainted the turn, and died on llama.cpp's
`image input is not supported - hint: ... you may need to provide the mmproj`. So the cost was
exactly what the entry claimed. The **wire** it proposed was the wrong one, and that is the finding
worth keeping: a child's argv is fixed at the *sidecar's* boot, so a swap's own `stop` then `start`
respawns the cortex tier from the same flags. Driven directly against the running control API,
`/props` answered `vision: true` before and after. The conductor would have re-probed on the one
event that cannot change the answer, and not on the one that does, which does not touch residency at
all.

What shipped instead is a port asked at the two moments the answer is acted on and cached nowhere.
`VisionProbe.can_see()` never raises and answers False when it cannot tell; `SightedToolRegistry`
drops `capture_screen` from the advertisement and **refuses it at the call**, which is the half that
protects the user, since a turn lists its tools once and then runs rounds against that list. Not
caching is what turns a bound on staleness into no staleness, and it is affordable by measurement
rather than by assumption: `/props` answers in 1.5 ms idle and 1.7 ms with a generation in flight
(worst of 40 samples 2.5 ms) against a capture that blits and PNG-encodes a display, so the probe's
timeout came *down*, from 5 s to 2 s, because it now sits inside a turn rather than at boot. The
objection the entry raised did not survive inspection: `vision.py` has always lived in the
composition root, never in `cortex_inference`, so re-probing never made the inference adapter
stateful. One thing the entry did not ask for came free, because the tool is registered whenever a
body exists and the probe runs per use: the advertisement now corrects itself in **both**
directions, so a deployment that gains a projector after boot no longer waits for a brain restart to
be seen.

## Trail

- 2026-07-19: the index recorded it in its pickup order for the first time, noting that it is no
  longer hypothetical, since the real swap restarts model servers and so the staleness it describes
  is reachable.
- 2026-08-06: landed, moving the area's count 13 to 12. Its cost was reproduced end to end and held
  while the wire it proposed was falsified, which is worth recording beside the cost estimates this
  backlog already warns about: an entry can name the right defect and the wrong trigger.
- 2026-08-06: that reading carried a second name off the Open items line, the outcome-driven capture
  indicator's, whose bullet had closed earlier the same day and whose decrement (14 to 13) the index
  had already recorded, so no count moved for it twice.
