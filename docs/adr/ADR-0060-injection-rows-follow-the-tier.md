# ADR-0060: Injection test rows start the server the way the tier ships it

**Status:** Accepted (2026-09-11)

## Context

The injection test, `brain/packages/inference/tests/test_injection_defense_live.py`, measures how
well the untrusted-content framing ([ADR-0013](ADR-0013-untrusted-content.md)) works on each
candidate of the model lineup, and its framed counts are one of the axes a pick is chosen on
([ADR-0004](ADR-0004-model-lineup.md)). Its image rows are
[ADR-0041](ADR-0041-injection-image-variant.md); this record covers how every row's server is started.

The test first started every server with one typed head, `-ngl 99 --ctx-size 8192 --parallel 1
--jinja`, sent the reasoning-off answer as a request key, and ran on the card only. The stack does
none of that: each tier has its own window and slot count, every subagent server has the
reasoning-off pair on its command line, and a stock deployment places the subagent tier on the CPU
under cgroup caps. A count taken that way described a server no deployment starts. The cortex rows
also ran at half their tier's window, and for a while the text rows included no cortex row at all.

## Decision

1. **A row starts with its tier's own command line.** A `Model` names the tier it is measured as
   (`CORTEX_TIER`, `BRAIN_TIER`, `SUBAGENT_TIER`, the logical ids the model host and the brain
   share). `tier_args` reads that tier's `TierArgs` off one `ModelHostConfig` with every artifact
   named, and `server_argv` hands it to the model host's own `llama_server_argv` with four things
   substituted: the artifact, the probe's port, the placement's layer count and the tail. A retuned
   tier therefore moves every row that measures it. Whether a model thinks is read off the tier's
   name
   ([R-558](../refinements/tasks/558-thinking-follows-the-tiers-name-and-not-its-shipped-budget.md)
   covers the case of a thinking tier started at a zero budget).

2. **The reasoning-off answer is a setting read off the tier.** `Switch` says where a row's answer
   comes from, `argv` or `request_key`. `shipped-argv` uses the subagent tier's own tail,
   `request-key` the JSON that tail's kwarg flag holds, decoded by `template_kwargs`, and
   `budget-alone` the budget half alone ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md)
   decision 16). The two forms are one value read twice, so no registry entry is owed; a tier that
   renamed a flag or dropped half the pair fails `test_switch_rows.py`, which CI runs. A tier that
   deliberates deliberately uses neither setting, so `repeat_of` gives it one row, under the shipped
   id.

3. **The layer count is a row for the one tier the stack places twice.** `PLACEMENTS` holds the card
   and the CPU, built on the core's `PlacementTarget`. The card row takes the tier's layer count off
   the model host; the CPU row takes `PlacementTarget.CPU.ngl`, runs the CPU image, is given no GPU
   device, and exists only under the shipped switch and only for the subagent tier. The pick's
   resistance had been measured only on the card, where a stock deployment does not run it.

4. **The CPU row applies every cap the subagents override sets.** `Placement.reservation` returns
   `--cpus` at `DEFAULT_CPU_BUDGET` and `--memory` and `--memory-swap` at `DEFAULT_MEM_BUDGET_GB`,
   the swap limit equal to the memory limit because that disables swap; `Placement.threads` appends
   `--threads` at the same CPU budget after the switch's flags. Both constants are imported, so the
   row uses what the scheduler admits against and the constant scan compares them with the compose
   file. Without the thread count a row runs one thread per hardware thread inside the quota, a
   shape the CPU subagent servers stopped running when their count was fixed
   ([ADR-0004](ADR-0004-model-lineup.md)).

5. **The engine images are declared by the test files and compared with what the stack uses.**
   `_GPU_IMAGE` here and `_IMAGE` in `test_unfenced_correction_live.py` and
   `test_uid_reading_live.py` declare the CUDA image, used by both `FROM` lines of
   `brain/Dockerfile.modelhost`; `_CPU_IMAGE` declares the CPU image, used by the three compose
   services that run it. `scripts/imagecouplings.py` is that part of the constant registry
   ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)). Each `FROM` search text is closed by the
   stage name or the line break, since a hyphen satisfies the scan's word-edge rule and a bare
   search text would pass a retag to `server-cuda-b10680`. An integration-marked test runs only when
   somebody measures, so nothing else would report it starting containers from a tag the stack had
   left.

6. **A server that exits reports itself.** `_await_health` reads the container's state between polls
   and fails with the last twelve lines of its log, so a missing artifact fails in seconds naming
   the file instead of using up the whole health timeout as though the weights were slow.

7. **A counted reply the two readings differ on is kept with both marks.** `test_reply_readings.py`
   holds in `RECORDED` each text-row reply a readings record quotes, with the judgement a hand sort
   gives it, and requires the structural reading ([ADR-0041](ADR-0041-injection-image-variant.md)
   decision 9) to agree on every one. It holds in `DIFFERING` each counted reply a hand sort reads
   apart from the structural reading, with both marks, and requires the structural reading to give
   the mark recorded for it. A row drawn at the engine's sampler counts up to 124 obeyed replies, so
   its other counted replies stay in its log.

## Consequences

- A row's count describes the server the stack starts. `test_switch_rows.py` requires a shipped
  text-only row to equal the model host's argv for the tier with only the artifact and port changed,
  the CPU row's caps and thread count in order, and the switch rows to differ by the setting alone.
- The cortex alternative is measured as `Qwen3.5-9B-UD-Q4_K_XL.gguf`, the 4-bit quant the models
  mount holds, since the `Q4_K_M` the candidate set names is not there.
- On the current lineup the two switch forms produce the same table and the CPU rows reproduce the
  card rows, so resistance reads as a property of the candidate rather than of the placement. The
  counts are in [injection text rows](../readings/injection-text-rows.md).
- A CPU row costs minutes rather than seconds, since it decodes on four CPUs; the image names
  written in dated measurements are not tied to anything, the tag being part of what was read.

## Alternatives rejected

- **Typing the head, the switch or the image into the test file**: each is a second copy of a value
  the stack declares, and one of them disagreed once already.
- **Running the CPU row on the quota alone**: the shipped pick's CPU server sits at nine tenths of
  its memory cap, so a row without the cap measures a shape no deployment runs.
- **A registry row for the two switch forms**: they are one value read twice, not two declarations
  to compare.

## Related

- [ADR-0004](ADR-0004-model-lineup.md), [ADR-0013](ADR-0013-untrusted-content.md),
  [ADR-0041](ADR-0041-injection-image-variant.md),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md),
  [ADR-0012](ADR-0012-resource-governance.md) (the two placements),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md).
- Runbook: [llamacpp-gpu](../runbooks/llamacpp-gpu.md) (running the test).
- Readings: [injection text rows](../readings/injection-text-rows.md).
