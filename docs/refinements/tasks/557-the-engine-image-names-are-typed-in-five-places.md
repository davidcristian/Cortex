# The engine image names are typed in several places

**Status:** done 2026-09-09
**Area:** inference
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

`_GPU_IMAGE` and `_CPU_IMAGE` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
write `ghcr.io/ggml-org/llama.cpp:server-cuda` and `ghcr.io/ggml-org/llama.cpp:server`. Read again
on 2026-09-08, the entry was wrong about its own subject twice: the count is eight files rather than
five, and one check already compared four of them.

Eight files contain a name something reads, and one of the eight arrived after this entry was filed.
`grep -rn 'ghcr\.io/ggml-org/llama\.cpp:server' --include='*.py' --include='*.yml' --include='Dockerfile*' brain/ docker/ scripts/ | grep -v scripts/tests/`
lists them: `docker/docker-compose.memory.yml`, `docker/docker-compose.subagents.yml` and
`docker/docker-compose.subagents-roster.yml` name `:server` on a service;
`brain/Dockerfile.modelhost` names `:server-cuda` on both its `FROM` lines;
`scripts/imagevolumes.py` keys a recorded row on each of the two names; and three live harnesses
type one or both,
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py),
[test_unfenced_correction_live.py](../../../brain/packages/orchestrator/tests/test_unfenced_correction_live.py)
and [test_uid_reading_live.py](../../../brain/packages/orchestrator/tests/test_uid_reading_live.py),
the last added 2026-09-06. Four more files name an image in prose alone (`trace_probe.py`,
`imagedrift.py`, `test_trace_budget_live.py` and `test_cut_tool_call_live.py`) and are not names
anything starts a server from.

A moved compose tag already fails `just check`. `scripts/crosscheck.py` compared none of these,
which is what the entry said, but `scripts/volumecheck.py` compares the deployment's names with the
two keys `scripts/imagevolumes.py` records, and it fails in both directions at once. Both halves
were proved on 2026-09-08 by editing the tree and running `python3 scripts/volumecheck.py`.

| edit | what the check reported |
| --- | --- |
| `docker-compose.subagents.yml` image to `:server-b10680` | `service 'llama-subagent' runs 'ghcr.io/ggml-org/llama.cpp:server-b10680', which scripts/imagevolumes.py has no row for` |
| `Dockerfile.modelhost` line 39 (final stage) to `:server-cuda-b10680` | the same for the base, plus `the record has a row for 'ghcr.io/ggml-org/llama.cpp:server-cuda', which nothing here names` |
| `Dockerfile.modelhost` line 18 (builder stage) to `:server-cuda-b10680` | `volumecheck OK`, the builder stage's base getting no row by design |

What was left uncompared was therefore four names and not eight: the builder stage's `FROM`, which
`dockerfilebases.py` skips because only the final stage's config survives a build, and the three
live harnesses. A retag on the stack is the case that mattered, because the check forces the compose
files and the final `FROM` to be corrected together and says nothing about the harnesses, which
would go on starting containers from the old tag.

## History

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which added the
  CPU image's name to the harness.
- 2026-09-08: read again against the tree. The count is eight files rather than five, a third
  harness having been added on 2026-09-06; `volumecheck.py` was measured to cover four of the names,
  and the builder stage's `FROM` measured not to be one of them. Moved to actionable with the
  comparison narrowed to the four that are unchecked. Recorded in the lineup-trigger reading of
  2026-09-08 ([ADR-0004](../../adr/ADR-0004-model-lineup.md)).
- 2026-09-09: done as `scripts/imagecouplings.py`, the registry's thirteenth part, holding two
  entries. The CUDA image is declared by all three harnesses and used by both `FROM` lines of
  `brain/Dockerfile.modelhost`; the CPU image is declared by `_CPU_IMAGE` and used by the three
  compose services that run it. The compose names are now compared twice over, by this check and by
  `volumecheck.py`, which is worth the overlap: this one reports the harness that has not moved and
  that one reports a record with no row. One lesson: a tag's hyphen is not a word boundary, so a
  bare `FROM {value}` search text fixed to two occurrences went on matching a line retagged to
  `server-cuda-b10680`, the guard at a word edge being `(?!\w)`, which a hyphen satisfies. Each
  `FROM` line now has a search text that closes it, the stage name after the builder's base and the
  line break after the final one. Nine mutations were shown to fail the check, two of them the
  reason for that closing text.
