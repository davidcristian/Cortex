# The couplings crosscheck.py did not cover

**Status:** done 2026-08-08
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

Once the constant scan existed with two registered entries, every unregistered pair of values that
must agree became a decision. A survey of the whole body and brain boundary on 2026-08-03 found
the rest, in four kinds.

1. **Relations the comparator cannot express.** The scan compares for equality, and three real
   pairs are orderings: the body's `MAX_EDGE_CEILING` (4096) must stay at or below the brain's
   `MAX_IMAGE_EDGE` (8192), the body's `CAPTURE_MIME` must stay inside the brain's
   `ALLOWED_MIME_TYPES`, and `cortex_body_client`'s `MAX_RECEIVE_BYTES` (16 MiB) must stay above
   both byte limits.
2. **Copies that are not declarations.** A value written inside a string is not read by a scan
   that reads constant declarations: `docker/docker-compose.yml`'s healthcheck contains
   `x-cortex-seam-token` inline in a one-line Python command, the brain's port `50051` appears in
   the shell as `"http://127.0.0.1:50051"` against `RpcServerConfig.port`, and the body's bind
   port `50151` is a bare literal argument in `body_server.rs` against a compose variable.
3. **TypeScript, for which the scan had no declaration syntax at all.** The overlay matched wire
   values by hand: `CAPTURE_SCREEN_TOOL` against the brain's `CAPTURE_SCREEN_TOOL_NAME`, whose
   divergence leaves the capture dot unlit, and a bare `"thinking"` literal in `turnState.ts` and
   twice in `Message.tsx` against `THINKING_STATE`, whose divergence leaves the reasoning trace
   unaccumulated and its chip unstyled. Both fail silently, by something never appearing.
4. **A name crossing from TypeScript into CSS**, where the far side is a use and not a
   declaration. `overlay/panelBudget.ts` declares `CEILING_PROPERTY` (`--ceiling`) and
   `overlay.css` reads it as `var(--ceiling, 100vh)`; rename either side and the fallback becomes
   the viewport, with every test still passing. The same form already covered `data-resizing`, and
   `overlay/measured.ts` adds `CHAT_FLOOR_PROPERTY` (`--chat-floor`) and `TRACE_ROW_PROPERTY`
   (`--trace-row`), read by `.log`'s floor and by the Thoughts disclosure, where a rename on
   either side falls back to the value declared on `:root` without an error.

One pair had already diverged, which is why this was recorded rather than done in passing.
`TITLE_MAX` was 48 in `brain/packages/core/src/cortex_core/sessions.py` and 32 in
`body/app/src/overlay/sessionState.ts`, while a comment above the brain's declaration claimed the
overlay applied the same rule. Measured in Chromium, a 42-character first message read in full in
its own switcher row and was cut at 33 characters in the header directly above it, both on screen
at once, in a header box that fits 42. The overlay moved to 48 on 2026-08-03, and the pair became
the registry's third entry and its first in TypeScript.

Closed 2026-08-08. The registry moved to `scripts/couplings.py` and went from 3 entries to 14,
behind two additions to the scan. `Relation.ORDERED` requires an entry's places to be in
non-decreasing order in registry order, and two of the three orderings are registered:
`MAX_EDGE_CEILING` at or below `MAX_IMAGE_EDGE`, and `MAX_CAPTURE_BYTES` at or below
`MAX_RECEIVE_BYTES`, stated against the body's limit rather than the brain's copy of it, because
the tree that produces the bytes is what the transport limit is about.

The second addition is the mention, and it answers three of the four kinds at once, which is the
finding rather than the feature: a key written inside a shell string, a stylesheet reading a name
back with `var(...)`, and a bare literal a component compares against are all the same problem,
that there is no declaration on that side to parse. A mention is a file plus a template containing
`{value}`; the scan renders the agreed value into the template and requires the result to appear
in the file. It is not circular, since the template gives the form and the file gives the value.
It also removed the work this entry expected: a bare literal never has to become a named constant,
because the check reads the use. So `thinking`, the healthcheck's fourth copy of the token key,
the four TypeScript-into-CSS names, the `--ease` curve and `capture_screen` are all covered.

One suite rule was relaxed deliberately: the test that rejected an entry confined to one top-level
tree now requires more than one suffix, since the overlay and its stylesheet are one tree and two
languages and are exactly the rename this scan is for. Two new rules replace it: the registry must
use both relations and both kinds of place, because a comparator no entry uses is the same defect
in a wider check. Nothing had diverged, so each new capability was made to fail on the real tree
once instead. What this opens is
[R-013](013-couplings-widened-registry-cannot-hold.md).

## History

- 2026-08-03: Opened after the constant scan was added, out of a survey of the whole body and
  brain boundary run before the registry was written. Three kinds needed three answers, and one
  pair, `TITLE_MAX`, had already diverged at 48 against 32, so registering it then would have
  turned a check on over a disagreement nobody had resolved.
- 2026-08-03: The TypeScript half closed later the same day when that disagreement was resolved,
  the overlay moving to 48, so the registry stood at three entries and the scan read TypeScript.
- 2026-08-08: Closed before anything diverged. The registry moved to `scripts/couplings.py` and
  went from 3 entries to 14 behind `Relation.ORDERED` and the mention form, the finding being that
  four of the five kinds are one missing feature. One suite rule was relaxed deliberately and two
  new ones replace what it lost. What it opens is the entry on the couplings the widened registry
  still cannot cover.
