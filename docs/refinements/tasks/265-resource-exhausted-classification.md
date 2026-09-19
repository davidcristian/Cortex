# `RESOURCE_EXHAUSTED` classification

**Status:** done 2026-08-08
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

A capture the halving ladder gives up on mapped to `Internal`, which is accurate but coarse: the
brain could not tell "your screen is too complex to send" from "the backend broke".

Re-read 2026-08-06 against the raised capture edge, with two findings. The first is that the
give-up case cannot be reached at the shipped byte ceiling at any edge the wire permits.
`Capture::from_bgra` runs three steps, each halving the edge the previous one reached, so the last
is at most a quarter of the requested edge: with `MAX_EDGE_CEILING` at 4096 that is 1024 px on the
long edge, at most 1024x1024 and 3.1 MB of raw RGB against a 6 MiB ceiling. PNG cannot inflate that
past the ceiling, so the third step always fits and `CaptureError::TooLarge` never happens. That is
written into `screen_policy.rs`'s own argument for why the byte ceiling travels with the request,
and the test that reaches the give-up branch does so by naming a 40-byte ceiling. Raising the edge
cannot change this, since the third step is a fraction of the edge. What would change it is a
deployment setting `CORTEX_BODY_MAX_IMAGE_BYTES` low enough that a quarter-edge capture can miss
it, which for the shipped 2048 px request is under roughly 450 KB, an eighth of its default.

The second finding was that nothing on the brain side read the status code:
`GrpcBodyGateway.capture_screen` catches `aio.AioRpcError` and keeps only `err.details()`, so what
reaches the model is the body's own sentence, and the three sentences are entirely different ("the
capture is too large for the wire: N bytes", "screen capture backend error: ...", "Deadline
Exceeded").

A separate wording defect on the same path was folded in here rather than counted separately.
`CaptureScreenTool.invoke` prefixed every failure with `could not reach the body to capture the
screen`, which is false for all but one of them: a refused capture, a broken backend, a reply the
gateway does not accept, and above all the shipping default, where `CORTEX_HOST_CAPTURE` is unset
and the body returns `PermissionDenied` promptly and precisely. The model was told the body is
unreachable and then, after the colon, the true reason. `volume.py` has the same prefix and is more
defensible there, having no kill switch behind it.

Both halves were done 2026-08-08 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md) decisions 8
to 10, the right home because what changed is the gateway's error vocabulary, and it changed for
volume and notify as much as for capture). The wording defect is reachable on an untouched install,
so the trigger had in fact occurred for the half nobody had counted as the trigger.

The 2026-08-06 re-read was right about the mechanism and wrong about the conclusion, and both
halves are worth keeping. Right: nothing on the brain side read the status code, verified again at
HEAD. Wrong: it concluded that the only reader already got the distinction, when what that reader
got was the body's sentence behind a lead sentence that contradicted it. The code nobody read was
exactly why the lead could not be chosen correctly, so the caller that would branch on a code was
in front of it the whole time. It is now `body_failure_message`.

What was built is one kind on the error (`BodyFailure`, six members: `UNREACHABLE`, `REFUSED`,
`UNSUPPORTED`, `UNREADY`, `OVERSIZE`, `FAULTED`), one status table in the adapter, one wording
table in the core, and on the body side a code per `CaptureError` variant rather than the one the
entry named. `TooLarge` moved to `ResourceExhausted` as written; `NoDisplay` moved to
`FailedPrecondition`, because it collided with the code tonic synthesizes for a channel that cannot
connect, which is the same indistinguishability one layer down and is why `AudioError::NoEndpoint`
and `NotifyError::Unavailable` moved with it. The ladder arithmetic is untouched and still true, so
this entry closed on the wording half while the classification half is a correctness fix nothing
can yet exercise from the outside.

## History

- 2026-07-18: Recorded when the vision slice was finished, with its trigger written as "the first
  time that coarseness sends a reader to the wrong place".
- 2026-08-06: Re-read against the raised capture edge and ruled not triggered, which was written
  down so that would be visibly a decision rather than an oversight. The pass was owed because
  `CORTEX_BODY_CAPTURE_MAX_EDGE` had moved from 0 to 2048 that morning, bringing the halving ladder
  nearer.
- 2026-08-06: That re-read also found something belonging to the region and window capture entry.
  The 74% of the byte ceiling the raised default had been approved with was a 4K number: a
  2560x1440 desktop under the same grain reaches 79%, because how much grain survives is set by the
  ratio between the display and the requested edge. The test that reads it was wrong in the other
  direction, calling an untouched 1920x1080 capture a halved one because it compared the returned
  width against the edge that was asked for rather than the edge that was possible.
- 2026-08-08: Closed whole, both the classification it is named for and the wording defect. The
  2026-08-06 re-read had been right on the mechanism and wrong on the conclusion. The deferral this
  close opened is not this area's; it is a coupling the constant check cannot handle, folded into
  [repo-checks.md](../index.md#repo-checks).
- 2026-08-09: A review read this work against the retryable-code table's trigger in
  [rpc-transport.md](../index.md#rpc-transport), which names a brain that starts returning
  `RESOURCE_EXHAUSTED` or `ABORTED`, and so looks triggered by what happened here. It is neither
  the same path nor the same direction. The code added here is raised by the body's own service for
  `CaptureError::TooLarge` and consumed by the brain as a client, which maps it to
  `BodyFailure.OVERSIZE`, while that retry policy classifies the body-to-brain direction in
  `body/crates/core/src/retry/policy.rs`, whose transient set is still exactly `Unavailable`.
