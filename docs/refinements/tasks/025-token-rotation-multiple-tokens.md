# Token rotation / multiple tokens

**Status:** open, dead until a consumer
**Area:** seam-auth
**Origin:** [ADR-0016](../../adr/ADR-0016-seam-token.md)
**Trigger:** A second client of the body↔brain seam exists.

Pointless for one user-managed body↔brain pair;
revisit with any second client (ADR-0016 deferred). The other ADR-0016 deferral, mTLS on a
non-loopback seam, is recorded at the Slice 9 hardened-posture entry (see
[body-gateway.md](../index.md#body-gateway)).

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc with the
  entry kept verbatim, and carried in the index's dead-until-a-consumer bucket as "Token rotation /
  multiple tokens: needs a second seam client".
