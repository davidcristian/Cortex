# A subagent server started outside compose is held by one value and not by the rule

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** a second hand-started subagent server appears in a runbook or a host task, or the one
that exists is found missing a flag the flag rule requires or spelling one with a value the shipped
stack does not
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19

Opened 2026-08-27 by the close of
[R-462](462-nothing-enumerates-the-subagent-servers-this-repo-starts.md), which held every subagent
server a composed stack starts to the flags its tier requires.

`docs/runbooks/subagents-cpu.md` hands an operator a `docker run` that brings up a standalone CPU
subagent server on loopback, outside any stack, carrying `--jinja`, the template kwarg,
`--reasoning-budget 0`, `--cache-ram 0` and, beside `-ngl 0`, `--threads 4`. A gate over compose
services cannot see it. What reaches the command block today is one constant-registry needle over
the budget's count, which came out of the same close: retune the tier's zero and that command block
fails the gate. That close registered two needles on this runbook, and the second is aimed at the
prose stating the pair rather than at the command. The four other flags the rule requires are held
there by nobody, and neither is the `--cpus 4` beside them, so an edit that dropped the kwarg from
the operator's command would leave the runbook telling somebody to start a server the shipped stack
would not. That is not a hypothetical any more: the rule gained the prompt-cache flag while the
command block stood still, and the command was three flags behind the shipped stack until
2026-09-14.

**Why it was left.** The scale is one command block in one runbook, and the shapes a fenced shell
line can take are the reason `samplecheck.py` exists as its own gate. Making the flag rule read
fenced commands is a second reader for one far side.

**What would close it.** Needles rather than a reader, for every flag but one. Three constants
already declare what the command spells, so a needle on this runbook needs no source edit:
`_JINJA` in the sidecar's `tiers.py` for `--jinja`, `_NO_PROMPT_CACHE` in its `config.py` for
`--cache-ram 0`, and the orchestrator's `DEFAULT_CPU_BUDGET` for both `--threads 4` and `--cpus 4`,
through `Spelling.WHOLE` because the constant declares `4.0`. `DEFAULT_CPU_BUDGET` already carries
the compose files' `--threads` needles, so those two are mentions on an existing entry, while
`_JINJA` and `_NO_PROMPT_CACHE` are registered nowhere yet and would each be a new entry. `_JINJA`
is not unheld all the same: `scripts/hostedtiers.py` reads the argv `llama_server_argv` returns and
holds every item in it to the flag gate's rule, so its `Flag("--jinja")` and the sidecar's `_JINJA`
fail together; what that reader cannot reach is the runbook. The kwarg is the one flag with no
constant to hang a needle off. `_SUBAGENT_TAIL` writes `'{"enable_thinking": false}'` inline, in
single quotes, inside a tuple of strings and names, and `scripts/values.py` reduces neither a
single-quoted string nor such a tuple. Declaring the kwarg as a constant of its own in the sidecar,
which is a brain edit, is not enough by itself: written in double quotes the JSON needs escapes,
and the string form raises on any backslash rather than decode it. So the kwarg needs both that
declaration and a value form that reads it, a single-quoted string being the smaller of the two
ways to write one. The alternative worth weighing first is that a
runbook command is prose an operator adapts, and holding five flags in it is holding a paste. The
reason to weigh it again is that adapting a paste is not what went wrong here: the rule moved and
the paste did not.

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
- 2026-09-19: re-derived and neither half of the trigger fired. The runbook's `docker run` is
  unchanged and carries all five flags the rule requires, the settings scan and the nearest-line
  report touched neither the command nor the flag rule, and no other subagent server is started by
  hand in `docs/`: `budget-probe` in `docs/runbooks/llamacpp-gpu.md` starts the cortex tier, and the
  CPU row that runbook describes is started by the live suite from the shipped argv rather than by
  an operator. The trigger's second clause named "the two flags the constant registry does not
  hold", a count that was stale by 2026-09-14, so it now names any required flag the command drops
  or respells. The remedy was wrong about the kwarg. It said `_SUBAGENT_TAIL` was a constant to hang
  the kwarg and the two counts off, but the value forms reduce no tuple of that shape and no
  single-quoted string, so only the counts have constants, `_NO_REASONING_BUDGET` (already
  registered) and `_NO_PROMPT_CACHE`. The paragraph now names the constant for each flag and says
  that the kwarg needs a declaration in the sidecar and a value form that can read it, since a
  double-quoted spelling of the JSON carries escapes the string form refuses.
