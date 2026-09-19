# A subagent server started outside compose is checked on one value and not by the rule

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** a second hand-started subagent server appears in a runbook or a host task, or the one
that exists is found missing a flag the flag rule requires or writing one with a value the shipped
stack does not use
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)
**Verified:** 2026-09-19

`docs/runbooks/subagents-cpu.md` gives an operator a `docker run` that starts a standalone CPU
subagent server on loopback, outside any stack, with `--jinja`, the template kwarg,
`--reasoning-budget 0`, `--cache-ram 0` and, beside `-ngl 0`, `--threads 4`. A check over compose
services cannot see it. What reaches the command block today is one constant-registry entry over
the budget's count, so retuning the tier's zero fails the check; a second entry covers the prose
that states the pair. The four other flags the rule requires are compared with nothing, and neither
is the `--cpus 4` beside them. This is not hypothetical: the rule gained the prompt-cache flag
while the command block stood still, and the command was three flags behind the shipped stack until
2026-09-14.

Closing it means registry entries rather than a reader, for every flag but one. Three constants
already declare what the command writes: `_JINJA` in the sidecar's `tiers.py` for `--jinja`,
`_NO_PROMPT_CACHE` in its `config.py` for `--cache-ram 0`, and the orchestrator's
`DEFAULT_CPU_BUDGET` for both `--threads 4` and `--cpus 4`, through `Spelling.WHOLE` because the
constant declares `4.0`. The kwarg is the one flag with no constant to reference: `_SUBAGENT_TAIL`
writes `'{"enable_thinking": false}'` inline, in single quotes, inside a tuple of strings and
names, and `scripts/values.py` reduces neither form. So the kwarg needs both a declaration in the
sidecar and a value form that reads it. The alternative worth weighing first is that a runbook
command is prose an operator adapts, so comparing five flags in it is comparing a paste; what went
wrong here was the rule moving while the paste did not.

## History

- 2026-08-27: opened by the close of
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), whose check reaches
  compose services and whose registry entry reaches this command block's budget alone.
- 2026-09-09: claims checked again and neither half of the trigger has fired. The runbook's
  `docker run` still uses all three flags, and the only other hand-started server in the docs is the
  cortex tier's forgotten-projector probe in `docs/runbooks/vision.md`, which is not a subagent
  server. Two claims here were wrong: the registry has two entries on this runbook rather than one,
  and `--jinja` is declared separately as `_JINJA` in the sidecar's `tiers.py` rather than being
  part of `_REASONING_OFF`.
- 2026-09-14: the second half of the trigger fired, from the rule's side. `flagcheck.REQUIREMENTS`
  then had three requirements, the reasoning-off pair, the tool-capable chat template and
  `--cache-ram 0`, the last added after this entry was opened, and the runbook's command had the
  first three and not the fourth, so it told an operator to start a server on llama.cpp's 8192 MiB
  host-RAM prompt cache. The command block now writes `--cache-ram 0` on its own line before the
  budget, so the registry entry over `\n  --reasoning-budget 0\n` still matches. `_REASONING_OFF`
  no longer exists in `config.py`; the tier's tail is `_SUBAGENT_TAIL` and it has three flags. And
  `_JINJA` is compared after all, by `scripts/hostedtiers.py` rather than by the registry.
- 2026-09-15: the rule gained a fourth requirement, a `--threads` on every server started with
  `-ngl 0`, and the runbook's command already wrote `-ngl 0 --threads 4`, so neither half of the
  trigger fired. The number of flags in that block that nothing compares rose from three to four:
  the kwarg, `--jinja`, `--cache-ram 0` and `--threads 4`. The CPU budget's constant has five
  registry entries and every one names a compose file, so the count beside `--cpus 4` is compared
  with nothing either.
- 2026-09-19: checked again and neither half of the trigger fired. The runbook's `docker run` is
  unchanged and has all five flags the rule requires, and no other subagent server is started by
  hand in `docs/`: `budget-probe` in `docs/runbooks/llamacpp-gpu.md` starts the cortex tier, and the
  CPU row that runbook describes is started by the live suite from the shipped argv. The trigger's
  second clause named a count of flags that was stale by 2026-09-14, so it now names any required
  flag the command drops or rewrites. The remedy was wrong about the kwarg: the value forms reduce
  no tuple of `_SUBAGENT_TAIL`'s shape and no single-quoted string, so only the counts have
  constants, `_NO_REASONING_BUDGET` (already registered) and `_NO_PROMPT_CACHE`.
