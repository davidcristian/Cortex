# A search string spanning two lines keeps the whole-file run and can name the wrong line

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)
**Verified:** 2026-10-10

Every search string without a newline moved to the per-line reading in `scripts/linereadings.py`.
The eight that contain one stay on the opening run over the whole file that
`searchtexts.longest_prefix` measures, which has the fault that reading was built to fix: an
opening satisfied on another line makes it longer than the mismatch on the line a reader means, and
a mismatch in the first characters leaves it stopping wherever else the file writes them. They are
listed by rendering every mention and keeping those containing `\n`.

Three have their newline at one end, in `docs/runbooks/subagents-cpu.md`,
`docs/runbooks/llamacpp-gpu.md` and `brain/Dockerfile.modelhost`. Each is one line with a boundary
attached, and the per-line reading could read it with that newline stripped. Five really cross a
line boundary: the two `--threads` strings in the two subagent compose files, the embedder's
`--batch-size` and `--ubatch-size` strings in `docker/docker-compose.memory.yml`, and
`built at the bound\nof {value} characters` in `docs/readings/embedding-input.md`. For those the
per-line reading would have to run over each window of two consecutive lines, which adds a loop to
`line_runs` and a window in place of a line number in the message. The readings one is a prose
sentence tied to where its paragraph wraps, so a rewrap alone fails the check; a search text on one
line of that sentence would remove it from the set without any change to the reader.

**Why it was left.** All eight are presence checks. The per-line reading was measured on
single-line search strings only, and its half floor and tie rule would need measuring again over
windows.

## History

- 2026-09-17: opened by the close of
  [R-406](406-the-quoted-run-of-an-unmatched-search-text-covers-a-whole-file.md), with the five counted by rendering
  the registry at that commit.
- 2026-09-24: read against the tree and not fired. Rendering all 320 mentions of the registry from
  a scratch script finds the same five containing a newline: the two `--threads` strings in
  `docker/docker-compose.subagents.yml` and `docker/docker-compose.subagents-roster.yml`,
  `\n  --reasoning-budget 0\n` in `docs/runbooks/subagents-cpu.md`, `\nCORTEX_IMAGE_MAX_TOKENS=1024`
  in `docs/runbooks/llamacpp-gpu.md` and `FROM ghcr.io/ggml-org/llama.cpp:server-cuda\n` in
  `brain/Dockerfile.modelhost`. The commits to `scripts/linereadings.py` and
  `scripts/searchtexts.py` since then rename names and reword printed text.
- 2026-10-03: not fired. Rendering all 321 mentions of the registry from a scratch script that
  calls `crosscheck.read_value` and `crosscheck.rendered` finds the same five containing a newline,
  each still a presence check with no occurrence count. `line_runs` in `scripts/linereadings.py`
  still returns nothing for a search string with a newline, so `searchtexts.unfound` reads those
  five by the run over the whole file. Neither module has a commit since 2026-09-24. The two
  registry commits since change entries in `scripts/endpointcouplings.py` and
  `scripts/wirecouplings.py`, add a TypeScript declaration form to `crosscheck.py` and let a Rust
  declaration hold a quoted `;`, and the newline count above is taken after them.
- 2026-10-10: fired. Rendering all 335 mentions with `crosscheck.read_value` and
  `crosscheck.rendered` finds eight containing a newline: the five above, and three registered on
  2026-10-07 in `scripts/shippedcouplings.py` beside the embedder's context and input bound, two in
  `docker/docker-compose.memory.yml` and one in `docs/readings/embedding-input.md`. All eight are
  presence checks with no occurrence count, and neither `scripts/linereadings.py` nor
  `scripts/searchtexts.py` has a commit since 2026-10-03, so `line_runs` still returns nothing for
  any of them. The task is actionable, and its account now names the eight.
