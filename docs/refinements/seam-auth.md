# Seam auth

Deferred refinements to the token authentication on the body↔brain gRPC seam, which
originates in [ADR-0016](../adr/ADR-0016-seam-token.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries
are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** token rotation / multiple tokens

**Seam auth ([ADR-0016](../adr/ADR-0016-seam-token.md)):**
- **Token rotation / multiple tokens.** Pointless for one user-managed body↔brain pair;
  revisit with any second client (ADR-0016 deferred). The other ADR-0016 deferral, mTLS on a
  non-loopback seam, is recorded at the Slice 9 hardened-posture entry (see
  [body-gateway.md](body-gateway.md)).
