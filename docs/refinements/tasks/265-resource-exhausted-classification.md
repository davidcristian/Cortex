# `RESOURCE_EXHAUSTED` classification

**Status:** landed 2026-08-08
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

A capture the ladder refuses maps to `Internal`, which
is honest but coarse: the brain cannot tell "your screen is too complex to send" from "the
backend broke". A distinct status (and a distinct message the cortex could relay) is a small
mapping change on both sides.

**Re-read 2026-08-06 against the raised capture edge, and it has not fired, for a reason that
outlives the numbers.** The trigger was re-read because `CORTEX_BODY_CAPTURE_MAX_EDGE` moved 0 to
2048 that morning, which brings the halving ladder nearer, and the sibling encoding entry below
had re-read itself against the same change while this one had not. Two findings, and the second
is the one that settles it.

The **arm this entry describes cannot be reached at the shipped byte ceiling at all**, at any
edge the seam permits. `Capture::from_bgra` runs three rungs, and each halves the edge the
previous rung *reached*, so the last rung is at most a quarter of the requested edge: with
`MAX_EDGE_CEILING` at 4096 that is 1024 px on the long edge, at most 1024x1024, and 3.1 MB of
raw RGB against a 6 MiB ceiling. PNG cannot inflate that past the ceiling, so the third rung
always fits and `CaptureError::TooLarge` never happens. This is not a discovery; it is written
into `screen_policy.rs`'s own argument for why the byte ceiling rides the request ("a branch
nothing can take is a gate that cannot fail"), and the gated test that reaches the give-up arm
reaches it by naming a 40 byte ceiling. Raising the *edge* cannot move this, because the third
rung is a fraction of the edge rather than a fixed size. What would move it is a deployment
setting `CORTEX_BODY_MAX_IMAGE_BYTES` low enough that a quarter-edge capture can miss it, which
for the shipped 2048 px ask is under roughly 450 KB, an eighth of its default. **So the trigger
is sharpened from a feeling to a check**: this entry fires when a deployment tightens that
budget far enough to make the give-up arm reachable, and not before.

The second finding narrows the coarseness the entry claims. The status *code* really is shared,
`Internal` for both `Backend` and `TooLarge`. But **nothing on the brain side reads the code**:
`GrpcBodyGateway.capture_screen` catches `aio.AioRpcError` and keeps only `err.details()`, so
what reaches the model is the body's own sentence, and the three sentences are entirely
different ("the capture is too large for the seam: N bytes", "screen capture backend error: ...",
"Deadline Exceeded"). The distinction the entry wants already reaches the only reader there is.
A code the brain does not read is worth adding for a caller that would branch on it, and there
is none yet.

**One live wording defect was found on the same path and is folded in here rather than counted
separately**, since one sitting fixes both and a near-duplicate name would inflate the area.
`CaptureScreenTool.invoke` prefixes every failure with `could not reach the body to capture the
screen`, which is false for all but one of them: a refused capture, a broken backend, a reply the
gateway will not vouch for, and above all the shipping default, where `CORTEX_HOST_CAPTURE` is
unset and the body answers `PermissionDenied` promptly and precisely. The model is told the body
is unreachable and then, after the colon, the true reason. It is a mis-framing rather than a lost
fact, which is why it waits, but it is reachable on a default install and this entry's own
trigger clause is about sending a reader to the wrong place. `volume.py` carries the same
prefix and is more defensible there, having no kill switch behind it.

**Both halves landed 2026-08-08, so this entry closes whole and the count moves 12 to 11**
([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)'s addendum of that date, which is the right
home because what changed is the gateway's error currency and it changed for volume and notify
as much as for capture). The wording half was the reason it stopped waiting: the prefix defect
is reachable on an untouched install and the entry's own trigger clause is about sending a
reader to the wrong place, so the trigger had in fact fired for the half nobody had counted as
the trigger.

**The 2026-08-06 re-read was right about the mechanism and wrong about the conclusion it drew
from it**, and both halves of that are worth keeping, since this file's standing warning is that
an entry records what somebody once measured. Right: nothing brain-side read the status code,
and that was verified again at HEAD before anything moved. Wrong: it read "the only reader
already gets the distinction" off that, when what the only reader got was the body's sentence
behind a lead that contradicted it. The code nobody read was exactly why the lead could not be
chosen correctly, so "a code the brain does not read is worth adding for a caller that would
branch on it, and there is none yet" had the caller in front of it the whole time. It is now
`body_failure_message`.

What landed is one kind on the error (`BodyFailure`, six members: `UNREACHABLE`, `REFUSED`,
`UNSUPPORTED`, `UNREADY`, `OVERSIZE`, `FAULTED`), one status table in the adapter, one wording
table in the core, and, on the body side, a code per `CaptureError` variant rather than the one
the entry named. `TooLarge` moved to `ResourceExhausted` as written; `NoDisplay` moved to
`FailedPrecondition` because it aliased with the code tonic synthesizes for a channel that
cannot connect, which is the same indistinguishability defect one layer down and is why
`AudioError::NoEndpoint` and `NotifyError::Unavailable` moved with it. The re-read's arithmetic
about the ladder is untouched and still true: `CaptureError::TooLarge` remains unreachable at the
shipped byte ceiling at any edge the seam permits, so this entry closed on the wording half
while the classification half is a correctness fix nothing can yet exercise from the outside.
A new deferral opens beside it, recorded below.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed, with its trigger written as
  "the first time that coarseness sends a reader to the wrong place".
- 2026-08-06: re-read against the raised capture edge and ruled not fired, which moved no count at
  all and was written down so that would be visibly a decision rather than an oversight. A re-read
  that confirms a deferral is the one event in this file that should leave the arithmetic exactly
  where it was. The pass was owed because `CORTEX_BODY_CAPTURE_MAX_EDGE` had moved 0 to 2048 that
  morning, bringing the halving ladder nearer, and the sibling encoding entry had re-read itself
  against the same change while this one had not.
- 2026-08-06: the index recorded a second thing that re-read found beside the wording defect, and it
  belongs to the neighbouring region and window capture entry rather than to this one. The 74% of
  the byte ceiling that morning's raised default had been signed off with was a 4K number: a
  2560x1440 desktop under the same grain reaches 79%, because how much grain survives is set by the
  ratio between the display and the requested edge rather than by the display's size, so the biggest
  display is the one that averages the most of it away. The margin holds and is smaller than it
  read, and the harness that reads it was wrong in the other direction, calling an untouched
  1920x1080 capture a fired ladder because it compared the returned width against the edge that was
  asked for rather than against the edge that was possible.
- 2026-08-08: closed whole, both the classification it is named for and the wording defect folded
  into it, moving the area's count 12 to 11. The 2026-08-06 re-read had counted it right on the
  mechanism and wrong on the conclusion: what it found, that nothing brain-side read the status
  code, was not a reason the distinction was already reaching its reader but the reason the reader
  could not be told the truth. The deferral this close opens is not this area's; it is a coupling
  the constant scan cannot hold, folded into [repo-gates.md](../index.md#repo-gates)'s existing entry rather
  than counted beside it, so no name arrived here to replace the one that left.
- 2026-08-09: a trigger sweep of the fix-when-it-bites bucket read this landing against the
  retryable-code table's trigger in [seam-transport.md](../index.md#seam-transport), which names a
  brain that starts answering `RESOURCE_EXHAUSTED` or `ABORTED` and so reads as fired by what landed
  here. It is neither the same path nor the same direction. The code this entry landed is raised by
  the body's own service for `CaptureError::TooLarge` (`body/crates/rpc/src/screen.rs:124`) and
  consumed by the brain as a client, which maps it to `BodyFailure.OVERSIZE`
  (`brain/packages/body_client/src/cortex_body_client/failures.py:40`), while that retry policy
  classifies the body-to-brain direction at `body/crates/core/src/retry/policy.rs:26`, whose
  transient set is still exactly `Unavailable`. That trigger wants a producer on the seam the policy
  reads, and what landed here is a producer on the other one.
