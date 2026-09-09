# The engine image names are typed in five places

**Status:** landed 2026-09-09
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which typed the
CPU engine image into the injection harness beside the CUDA one already there.

`_GPU_IMAGE` and `_CPU_IMAGE` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
spell `ghcr.io/ggml-org/llama.cpp:server-cuda` and `ghcr.io/ggml-org/llama.cpp:server`.

**Re-read 2026-09-08, and the entry was wrong about its own subject twice.** The count is one, and
what holds the spellings is the other.

**Eight files carry a spelling something reads**, not five, and one of the eight arrived after this
entry was filed. `grep -rn 'ghcr\.io/ggml-org/llama\.cpp:server' --include='*.py' --include='*.yml'
--include='Dockerfile*' brain/ docker/ scripts/ | grep -v scripts/tests/` lists them:
`docker/docker-compose.memory.yml`, `docker/docker-compose.subagents.yml` and
`docker/docker-compose.subagents-roster.yml` name `:server` on a service; `brain/Dockerfile.modelhost`
names `:server-cuda` on both its `FROM` lines; `scripts/imagevolumes.py` keys a recorded row on each
of the two names; and three live harnesses type one or both,
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py),
[test_unfenced_correction_live.py](../../../brain/packages/orchestrator/tests/test_unfenced_correction_live.py)
and
[test_uid_reading_live.py](../../../brain/packages/orchestrator/tests/test_uid_reading_live.py),
the last of which was added 2026-09-06, a day after this entry was written. Four more files name an
image in prose alone (`lever.py`, `imagedrift.py`, `test_trace_budget_live.py` and
`test_cut_tool_call_live.py`) and are not spellings anything starts a server from.

**A moved compose tag already fails `just check`,** so the trigger this entry was filed with named
an event a gate reports. `scripts/crosscheck.py` held none of these equal, which is what the entry
said, but `scripts/volumecheck.py` holds the deployment's spellings to the two keys
`scripts/imagevolumes.py` records, and it fails in both directions at once: the compose image has no
row, and the recorded row is then named by nothing. Both halves were proved on 2026-09-08 by editing
the tree and running `python3 scripts/volumecheck.py`.

| edit | what the gate reported |
| --- | --- |
| `docker-compose.subagents.yml` image to `:server-b10680` | `service 'llama-subagent' runs 'ghcr.io/ggml-org/llama.cpp:server-b10680', which scripts/imagevolumes.py has no row for` |
| `Dockerfile.modelhost` line 39 (final stage) to `:server-cuda-b10680` | the same for the base, plus `the record has a row for 'ghcr.io/ggml-org/llama.cpp:server-cuda', which nothing here names` |
| `Dockerfile.modelhost` line 18 (builder stage) to `:server-cuda-b10680` | `volumecheck OK`, the builder stage's base getting no row by design |

**What was left uncoupled** was therefore four spellings and not eight: the builder stage's `FROM`,
which `dockerfilebases.py` skips because only the final stage's config survives a build, and the
three live harnesses. A retag on the stack is the case that mattered, because the gate forces the
compose files and the final `FROM` to be corrected together and said nothing about the harnesses,
which would go on starting containers from the old tag.

**Landed 2026-09-09 as a registry part of its own,** `scripts/imagecouplings.py`, holding two
entries. The CUDA image is declared by all three harnesses and spent by both `FROM` lines of
`brain/Dockerfile.modelhost`; the CPU image is declared by `_CPU_IMAGE` and spent by the three
compose services that run it. The compose spellings are held twice over now, by this gate and by
`volumecheck.py`, which is worth the overlap: this one reports the harness that has not moved and
that one reports a record with no row.

**A tag's hyphen is not a word boundary,** which the first draft of the entry failed on. A bare
`FROM {value}` needle pinned to two occurrences went on matching a line retagged to
`server-cuda-b10680`, a rendered needle being required to appear as a token of its own and the
guard at a word edge being `(?!\w)`, which a hyphen satisfies. Each `FROM` line now carries a
needle that closes it, the stage name after the builder's base and the line break after the final
one. The mutation table for all nine spellings is in the
[ADR-0004 image-coupling addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-09-the-engine-image-is-one-value-the-harnesses-declare-and-the-stack-spends).

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which added
  the CPU image's spelling to the harness.
- 2026-09-08: re-read against the tree. The count is eight files rather than five, a third harness
  having been added on 2026-09-06; `volumecheck.py` was measured to hold four of the spellings, and
  the builder stage's `FROM` measured not to be one of them. Moved to actionable with the coupling
  narrowed to the four that float. Recorded in the
  [ADR-0004 lineup-trigger addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-08-three-lineup-triggers-re-read-and-a-memory-cap-already-at-90-of-its-limit).
- 2026-09-09: landed as `scripts/imagecouplings.py`, the registry's thirteenth part, with nine
  mutations shown to fail the gate and two of those nine the reason the needles carry what closes
  a `FROM` line.
