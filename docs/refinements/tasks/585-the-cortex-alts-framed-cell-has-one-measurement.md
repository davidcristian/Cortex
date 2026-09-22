# The cortex alt's framed cell has one measurement and three changes under it

**Status:** done 2026-09-06
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The lineup table and the first table of [ADR-0013](../../adr/ADR-0013-untrusted-content.md) publish
Qwen3.5-9B at 0 of 10 framed, a mention count. The row drawn on 2026-09-06 is 1 of 10 framed obeyed
and mentioned, the firing being `conditional-trigger`, with 4 of 10 unframed. Three things changed
between the two: the artifact is the mount's `UD-Q4_K_XL` where the published count was drawn on the
`Q4_K_M` name, the window is the cortex tier's 16384 where it was 8192, and reasoning is turned off
by the tier's own command line where it was a request key. One firing in ten is also inside the
spread a single run of a ten-attack row has.

## History

- 2026-09-06: opened by the close of
  [R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md),
  whose 2026-09-06 change of artifact ([ADR-0004](../../adr/ADR-0004-model-lineup.md)) publishes the
  row and names the three changes.
- 2026-09-06: done, an hour after it was opened. Two more runs read the framed count at 0 and 1
  against the first's 1, so the published 0 of 10 is inside this row's spread and the move is not a
  real change in the cell. One of the three changes the entry names is not a change: a thinking-on
  tier has one switch row, and the harness that published the count sent its request key on
  thinking-off rows alone, so only the quant and the window differ. The window was then held at the
  published 8192 through `CORTEX_CTX_SIZE` with everything else unchanged, and the row fired the
  same one attack. The quant cannot be isolated while the mount holds no `Q4_K_M`. The 2026-09-06
  spread readings ([injection text rows](../../readings/injection-text-rows.md)) publish all three
  runs.
