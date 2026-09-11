# The five-pick envelope table is on an image the stack no longer pulls

**Status:** landed 2026-09-11
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-09-11. The row addendum at the origin tables the five subagent picks at 288 runs each,
and every row of that table was drawn on llama.cpp `b10644-d7a207411` from
`ghcr.io/ggml-org/llama.cpp@sha256:9f0a986a78ab`. The `server-cuda` tag now resolves to
`sha256:952424b09abc` (`b10680-d7bd3bfca`), and the CPU `server` tag the subagent compose file names
serves the same build, so no row of the table describes the image the stack pulls. The
sweep-columns addendum drew the smallest pick once on the new image and found two of its nine cells
outside the tabled intervals: the constrained lookup at 18 of 32 against 0.65 to 0.91, and the
constrained extraction at 7 of 32 against 0.23 to 0.55. The lapse addendum then corrected the judge
the table's rule is read by, adding the body handed back as a lapse and refusing a lookup reply
that names an instance its body does not state, and it names this re-tabling as the reading those
rules are first read in.

**What would close it.** The row addendum's design drawn again for all five picks on the current
image, seeded from 1, with the samples kept under `measurements/` so a later rule change re-reads
them without the GPU, and published at the origin with the old rule's column beside the corrected
one for every pick and the reasoning-channel table re-read on the new build. The old table stays
as the dated reading it is, and every sentence quoting one of its cells as current points at the
new one. No model pick moves here; a pick the new table argues against is a recommendation.

## Pre-registration

Written 2026-09-11 at 05:19, before the first server of this re-tabling started. "Outside" means a
machine count, read at the tabled reading (comma charitable, refusal strict, naming strict) under
the rule the table was read under, falling outside the Wilson interval the row addendum prints
beside that cell.

1. **The smallest pick** keeps the two cells above outside and no other of its nine, since its
   cells are the sweep-columns addendum's seeded samples. A redraw of that pick carrying the
   compose file's `--threads` and cgroup caps, which that sweep's server did not carry, pairs with
   those samples on at least 280 of 288 cells, and any cell that differs is a body's first request
   on the fresh server. Neither change reaches a reply when every layer is on the card.
2. **The other four picks**, 36 cells: 1 to 4 fall outside, all on cells the table shows off the
   ceiling (the E4B's bare summarization, the 2B's extraction and lookup cells, the E2B's bare
   summarization and constrained lookup and extraction, the 4B's extraction cells). No direction is
   predicted for the two gemma-4-E picks. If the smallest pick's lookup drop is the build's rather
   than the sample's, the 2B's and 4B's constrained lookup cells fall with it; the expectation is
   that they do not.
3. **The copy lapse** subtracts only on the summarization and extraction cells of the `bare` and
   `constrained` arms. On the smallest pick that is 7, 3, 6 and 1, as the lapse addendum read it; on
   the 2B, 1 to 4 on each of its bare summarization and bare extraction; and 0 or 1 on each such cell
   of the E4B, the E2B and the 4B.
4. **The invented-instance refusal** subtracts only on lookup cells, on every arm, the control
   included, most of it on the clinic body, which names no month. On the smallest pick that is 10,
   9 and 7; on the 2B, 3 to 8 a cell; on the E4B, the E2B and the 4B, 0 to 4 a cell.
5. **The floor** refuses the lookup comparison of the smallest pick and of no other pick, which
   needs each other pick's control lookup to keep at least 26 of 32 under the corrected rule.
6. **The reasoning channel**: no run of a Qwen pick writes to it, 0 of 288 each, and the E4B's and
   E2B's constrained arms write to it at rates inside the intervals the row addendum prints for
   8 of 96 and 14 of 96.

## Trail

- 2026-09-11: opened by the decision to re-table the five picks, on the sweep-columns
  addendum's two cells and the lapse addendum's rules. Read at 05:18 before anything started: the
  local `server-cuda` image is `sha256:952424b09abc`, the image the smallest pick's sweep ran on;
  `brain/packages/orchestrator/tests/test_envelope_cost_live.py` and the orchestrator package are
  unchanged since the commit that added the seed, so the harness has not moved since that sweep;
  no container was running, the card read 3010 MiB used with nothing on it, and the load average
  was 0.25.
- 2026-09-11: landed by the re-table addendum at the origin. All five picks were drawn seeded on
  `sha256:952424b09abc` with the compose file's argv, `--threads 4.0` included, and its three caps,
  one server at a time at `-ngl 99`, and published one shape at a time under the corrected rules.
  The smallest pick's sweep was reused, and a redraw paired with it on 288 of 288 cells. The 4B's
  first server was killed by the memory cap after 67 completions and was drawn again without it; the
  67 finished cells paired. Under the corrected rules the shipped path reads 77, 59, 54, 42 and 70
  of 96 on the E4B, the 2B, the E2B, the 0.8B and the 4B, where the old table read 90, 83, 84, 66
  and 94, and 99 of the 109 runs the correction takes off the constrained arms are the report
  handed back on the summarization. Scored against the pre-registration above: items 5 and 6 held,
  item 4 held on 13 of 15 cells, items 1 and 2 missed a count by one, and item 3 missed by an order
  of magnitude. Opened
  [R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md), the sentence that
  draws the copy, and
  [R-642](642-the-engines-prompt-cache-may-grow-to-the-whole-memory-cap.md), the prompt cache that
  outgrew the cap. The samples are under `measurements/envelope-retable-2026-09-11/`, one directory
  per pick, with the smallest pick's redraw beside it as `qwen3.5-0.8b-redraw`.
