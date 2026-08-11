# Readings: what the cortex reads when a body call fails

The sentence a body built-in hands the cortex for each way a `BodyService` call can fail, before and
after the gateway's failures gained a kind. Cited by
[ADR-0023](../adr/ADR-0023-body-gateway-volume.md), decisions 8 to 10.

## Before: one lead for every failure

**2026-08-08.** The real `GrpcBodyGateway` driven against a loopback `BodyService` answering the
codes and sentences `body/crates/rpc/src/screen.rs` and `server.rs` then wrote, plus a body that was
not there. Each built-in prefixed every failure with a fixed lead.

| Failure | Code the body sent | Lead the cortex read |
| --- | --- | --- |
| capture switched off (`CORTEX_HOST_CAPTURE` unset, the shipping default) | `PERMISSION_DENIED` | `could not reach the body` |
| capture too large even downscaled | `INTERNAL` | `could not reach the body` |
| no display (lid shut, headless) | `UNAVAILABLE` | `could not reach the body` |
| capture backend fault | `INTERNAL` | `could not reach the body` |
| a body built before the capture RPC | `UNIMPLEMENTED` | `could not reach the body` |
| wrong or missing `CORTEX_SEAM_TOKEN` | `UNAUTHENTICATED` | `could not reach the body` |
| body absent | none, synthesized by the client | `could not reach the body` |
| no audio endpoint | `UNAVAILABLE` | `could not reach the body` |

One row in eight was true. In the other seven the body had answered, and the real reason followed
the false lead after a colon. The first row is what a default install gets on its first capture.

## After: the lead follows the kind

**2026-08-08.** Same harness, after the change. The detail after the colon is the body's own
sentence and is unchanged, so only the lead is shown.

| Failure | Code | Kind | Lead |
| --- | --- | --- | --- |
| capture switched off | `PERMISSION_DENIED` | `REFUSED` | `the body refused to capture the screen` |
| capture too large | `RESOURCE_EXHAUSTED` | `OVERSIZE` | `the body could not capture the screen within the size the seam allows` |
| no display | `FAILED_PRECONDITION` | `UNREADY` | `the host is not in a state to capture the screen` |
| capture backend fault | `INTERNAL` | `FAULTED` | `the body failed to capture the screen` |
| a body built before the capture RPC | `UNIMPLEMENTED` | `UNSUPPORTED` | `this body has no way to capture the screen` |
| wrong or missing `CORTEX_SEAM_TOKEN` | `UNAUTHENTICATED` | `REFUSED` | `the body refused to capture the screen` |
| body absent | synthesized | `UNREACHABLE` | `could not reach the body to capture the screen` |
| no audio endpoint | `FAILED_PRECONDITION` | `UNREADY` | `the host is not in a state to control volume` |

The absent body's detail reads `Deadline Exceeded` rather than a connection error, because the
capture call is sent with a deadline and a fresh channel retries the dial until it elapses. Both
codes classify as `UNREACHABLE`.

**Older body.** Run once more against a body still sending the earlier codes, a shut lid
(`UNAVAILABLE`) reads back as could not reach the body, and a too-large capture (`INTERNAL`) as
the body failed to capture the screen. An older body gets the earlier sentence, never a wrong new
one.

**Across the language boundary.** The real tonic `body_service` over loopback with
`DeniedScreenCapture`, the backend a default install runs, answered by the real `GrpcBodyGateway`:
`PERMISSION_DENIED` on the wire, `REFUSED` as the kind, and the refused lead in the tool result.

Method: `brain/packages/body_client/tests/test_gateway.py` asserts the classification per code and
`brain/packages/core/tests/test_body_failure.py` the lead per kind. The rows a real GDI backend
alone produces (a shut lid, a failed `BitBlt`) have not been read from real hardware; that work is
[H-012](../host/tasks/012-display-capture-path.md).
