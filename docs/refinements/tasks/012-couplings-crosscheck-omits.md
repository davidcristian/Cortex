# The couplings crosscheck.py does not hold yet

**Status:** landed 2026-08-08
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-03 behind the scan landing, because a registry with two entries makes every unregistered
coupling a decision rather than an absence. A survey of the whole seam on that day, run before
the registry was written rather than after, found the rest, and they fall into three kinds that
need three different answers. **First, relations the comparator cannot express.** The scan
compares for equality, and three real couplings are orderings: the body's `MAX_EDGE_CEILING`
(4096) must stay at or below the brain's `MAX_IMAGE_EDGE` (8192), the body's `CAPTURE_MIME`
must stay inside the brain's `ALLOWED_MIME_TYPES`, and `cortex_body_client`'s
`MAX_RECEIVE_BYTES` (16 MiB) must stay above both byte ceilings. Each would need a comparator
and a registry field naming which one applies, which is a design, not a line.
**Second, copies that are not declarations.** A value spelled inside a string is not read by a
scan that reads constant declarations: `docker/docker-compose.yml`'s healthcheck carries
`x-cortex-seam-token` inline in a one-line Python command (a fourth copy of a key the gate now
ties in three places, and the one whose drift nothing would report), the brain's port `50051` lives
in the shell as `"http://127.0.0.1:50051"` against `SeamServerConfig.port`, and the body's bind
port `50151` is a bare literal argument in `body_server.rs` against a compose env var. Teaching
a constant scanner to read a shell string embedded in YAML is a different tool. **Third,
TypeScript, which the scan had no declaration syntax for at all. That half closed the same day
(below), so what remains of this kind is the naming, not the scanning.** The overlay matches wire
values by hand: `CAPTURE_SCREEN_TOOL` against the brain's `CAPTURE_SCREEN_TOOL_NAME`, whose
drift leaves the capture dot unlit, and a bare `"thinking"` literal (in `turnState.ts` and
twice in `Message.tsx`) against `THINKING_STATE`, whose drift leaves the reasoning trace
unaccumulated and its chip unstyled. Both fail without an error, by a surface never appearing.
`CAPTURE_SCREEN_TOOL` is now registrable as it stands, at the cost of a registry entry; the
`"thinking"` literals are not, and deciding that a bare literal must first become a named
constant is the work that is left. **A fourth kind arrived on 2026-08-03 and is the same
entry rather than a new one:** a name that crosses from TypeScript into CSS, where the far side
is a USE and not a declaration at all, so there is nothing for a declaration scanner to compare.
`overlay/panelBudget.ts` publishes `CEILING_PROPERTY` (`--ceiling`) and overlay.css spends it as
`var(--ceiling, 100vh)`; rename either side and the fallback becomes the viewport, which
is the uncapped section the panel's budget exists to stop, with every test still passing
([ADR-0035](../../adr/ADR-0035-console-and-motion.md), the 2026-08-03 budget addendum). The same
shape already holds `data-resizing`, written by the placement and read only by the rule that
hides the history's thumb, and gained two more members later the same day: `overlay/measured.ts`
publishes `CHAT_FLOOR_PROPERTY` (`--chat-floor`) and `TRACE_ROW_PROPERTY` (`--trace-row`), spent
by `.log`'s floor and by the settled Thoughts disclosure, where a rename on either side falls back
to the value declared on `:root` and so degrades to exactly the frozen constants the probe
replaced, without an error and with every test passing ([ADR-0035](../../adr/ADR-0035-console-and-motion.md),
the 2026-08-03 chat-floor addendum). All four are pinned as literals in their own suites,
and that is the only thing standing in a rename's way today; what would close it is a scan that
reads a stylesheet for uses rather than a source for declarations.
**One of them was already divergent, which is why this was recorded rather than folded in, and
that one is settled and registered as of 2026-08-03 (the same day, later).** `TITLE_MAX` was 48
in `brain/packages/core/src/cortex_core/sessions.py` and 32 in
`body/app/src/overlay/sessionState.ts`, and the comment above the brain's declaration said the
overlay "applies the same rule and is kept documented in step, since neither side can see the
other's constant". It did not. This entry's framing of the artefact, taken from
[ADR-0021](../../adr/ADR-0021-session-read-seam.md), was also narrower than the code: it named the
chat being loaded, where the header-title carry had already closed the gap, and the path the 32
actually governed was the chat being **had**, whose header `turnState.submit` writes from the
local derivation and never revisits. Measured in Chromium, a 42-character first message read in
full in that chat's own switcher row and cut at 33 characters in the header directly above it,
both on screen at once, in a header box that fits 42 and so was not short of room. The overlay
is now 48, the pair is the registry's third entry and the first in TypeScript, and the gate was
proved to fail on a divergence before being trusted (ADR-0021 truncation addendum, 2026-08-03).
**What is left of this entry:** a comparator field for the ordered relations, the copies that
are not declarations, and the TypeScript-into-CSS names whose far side is a use. **Trigger:**
the first coupling that actually drifts.

**Landed 2026-08-08, four of the five kinds, and one of them turned out to be three**
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md), the 2026-08-08 registry addendum). The
registry moved to `scripts/couplings.py` and went from 3 entries to 14, behind two additions to
the scan. **The comparator field** is `Relation.ORDERED`, holding an entry's sites to
non-decreasing order in registry order, and two of the three orderings this entry named are
registered: `MAX_EDGE_CEILING` at or below `MAX_IMAGE_EDGE`, and `MAX_CAPTURE_BYTES` at or below
`MAX_RECEIVE_BYTES`, stated against the body's ceiling rather than the brain's copy of it,
because the tree that produces the bytes is the one the transport limit is really about.
**The mention** is the other addition, and it answers three of the five kinds at once, which is
the finding rather than the feature: a key spelled inside a shell string, a stylesheet reading a
name back with `var(...)`, and a bare literal a component compares against are one problem, that
there is no declaration on that side to parse. A mention is a file plus a template carrying
`{value}`; the scan renders the agreed value into it and requires the result to appear. It is
not circular, the template carrying the shape and the site the value, and it dissolves the work
this entry thought was left in the `thinking` case: a bare literal never has to become a named
constant, because the check reads the use rather than a declaration. So `thinking`, the
healthcheck's fourth copy of the seam-token key, the four TypeScript-into-CSS names, the
`--ease` curve, and `capture_screen` (which needed nothing but registering) are all tied now.
**One suite invariant was relaxed deliberately** and is recorded here rather than left implicit: the test that refused an
entry confined to one top-level tree now demands more than one suffix, since the overlay and its
stylesheet are one tree and two languages and are exactly the rename this scan is for. Two new
invariants replace what that loses, both aimed at this widening rather than at the tree: the
registry must exercise both relations and both kinds of place, because a comparator no entry
uses is the same defect in a wider gate. **Landed ahead of the trigger**, which was the first
coupling that actually drifts; nothing had drifted, and each capability was made to fail on the
real tree instead, once per capability. **What this opens** is the entry below.

## Trail

- 2026-08-03: Opened behind the constant scan landing, taking vision from 18 entries to 17 and
  this area from four to five, out of a survey of the whole seam run before the registry was
  written rather than after. Three kinds needed three answers, and one coupling, `TITLE_MAX`, was
  already divergent at 48 against 32, so registering it then would have turned a gate on over a
  shipped disagreement nobody had decided how to resolve.
- 2026-08-03: The TypeScript half closed later the same day when that disagreement was decided,
  the overlay moving to 48, so the registry stood at three entries and the scan read TypeScript.
- 2026-08-08: Struck ahead of its trigger, which was the first coupling that actually drifts. The
  registry moved to `scripts/couplings.py` and went from 3 entries to 14 behind `Relation.ORDERED`
  and the mention form, the finding being that four of the five kinds are one missing feature. One
  suite invariant was relaxed deliberately and two new ones replace what it lost. What it opens is
  the entry on the couplings the widened registry still cannot hold.
