# A subagent server started outside compose is held by one value and not by the rule

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a second hand-started subagent server appears in a runbook or a host task, or one of
the two flags the constant registry does not hold is found missing from the one that exists
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-15

Opened 2026-08-27 by the close of
[R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which held every subagent
server a composed stack starts to the flags its tier requires.

`docs/runbooks/subagents-cpu.md` hands an operator a `docker run` that brings up a standalone CPU
subagent server on loopback, outside any stack, carrying `--jinja`, the template kwarg,
`--reasoning-budget 0` and `--cache-ram 0`. A gate over compose services cannot see it. What
reaches the command block today is one constant-registry needle over the budget's count, which came
out of the same close: retune the tier's zero and that command block fails the gate. That close
registered two needles on this runbook, and the second is aimed at the prose stating the pair
rather than at the command. The three other flags are held there by nobody, so an
edit that dropped the kwarg from the operator's command would leave the runbook telling somebody to
start a server the shipped stack would not. That is not a hypothetical any more: the rule gained
the prompt-cache flag while the command block stood still, and the command was three flags behind
the shipped stack until 2026-09-14.

**Why it was left.** The scale is one command block in one runbook, and the shapes a fenced shell
line can take are the reason `samplecheck.py` exists as its own gate. Making the flag rule read
fenced commands is a second reader for one far side.

**What would close it.** Most likely three more needles rather than a reader: the kwarg, the
`--jinja` and the prompt cache's count are each a fixed string, and each has a constant in the
sidecar to hang off, `_SUBAGENT_TAIL` in `config.py` for the kwarg and the two counts and `_JINJA`
in `tiers.py` for the other. None of those strings is registered in the constant registry, though
`_JINJA` is no longer unheld: `scripts/hostedtiers.py` reads the argv `llama_server_argv` returns
and holds every item in it to the flag gate's rule, so its `Flag("--jinja")` and the
sidecar's `_JINJA` do fail together. What that reader cannot reach is the runbook, which is the
whole of what this entry is about. The alternative worth weighing first is that a runbook command
is prose an operator adapts, and holding four flags in it is holding a paste. The reason to weigh
it again is that adapting a paste is not what went wrong here: the rule moved and the paste did
not.

## Trail

- 2026-08-27: opened by the close of
  [R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), whose gate reaches
  compose services and whose registry entry reaches this command block's budget alone.
- 2026-09-09: claims re-derived and the trigger has not fired on either half. The runbook's
  `docker run` still carries all three flags, and the only other hand-started server in the docs
  is the cortex tier's forgotten-projector probe in `docs/runbooks/vision.md`, which is not a
  subagent server and spells no reasoning budget. Two claims here were wrong. The registry carries
  two needles on this runbook rather than one, both landed by the opening close, the second over
  the prose that states the pair; and `--jinja` is not in `_REASONING_OFF`, which holds
  `--chat-template-kwargs`, the kwarg and the budget's count. `--jinja` is declared separately as
  `_JINJA` in the sidecar's `tiers.py`, so the remedy is two constants rather than one.
- 2026-09-14: the second half of the trigger fired, from the rule's side rather than from an edit
  to the command. `flagcheck.REQUIREMENTS` carries three requirements today, the reasoning-off
  pair, the tool-capable chat template and `--cache-ram 0`, the last added after this entry was
  opened. The runbook's `docker run` carried the first three flags and not the fourth, so it was
  telling an operator to start a server on llama.cpp's 8192 MiB host-RAM prompt cache while every
  server the shipped stack starts turns it off. The command block now spells `--cache-ram 0`, on
  its own line before the budget so the registry needle over `\n  --reasoning-budget 0\n` still
  matches. Two claims above were also wrong. `_REASONING_OFF` no longer exists in `config.py`; the
  tier's tail is `_SUBAGENT_TAIL` and it carries three flags rather than two, the kwarg, the budget
  and the cache. And `_JINJA` is held after all, not by the constant registry but by
  `scripts/hostedtiers.py`, which reduces the argv builder's return tuple and compares it against
  the flag rule, so a rename on either side fails. The entry stays open because none of that
  reaches a fenced command in a runbook, which is the one far side it names.
- 2026-09-15: the rule moved again and this time the paste was already ahead of it. The flag gate
  gained a fourth requirement, a `--threads` on every server started with `-ngl 0`, and the
  runbook's `docker run` already spells `-ngl 0 --threads 4`, added when the thread pin landed. So
  neither half of the trigger fired. The count of flags in that command block that nothing holds
  rose from three to four all the same: the kwarg, `--jinja`, `--cache-ram 0` and now `--threads 4`.
  The CPU budget's own constant carries five needles and every one of them names a compose file, so
  the count beside `--cpus 4` in this block is held by nobody either, which is a second value of the
  same kind rather than a second far side. The entry stays open, and what it is about is unchanged:
  a fenced command in a runbook is the one far side a rule over compose services cannot reach.
