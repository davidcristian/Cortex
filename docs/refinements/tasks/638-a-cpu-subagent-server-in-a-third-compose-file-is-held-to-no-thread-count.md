# A CPU subagent server in a third compose file is held to no thread count

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a compose file other than `docker/docker-compose.subagents.yml` and
`docker/docker-compose.subagents-roster.yml` that starts a subagent server with `-ngl 0`, which
`uv run python flagcheck.py --root ..` in `scripts/` counts in its success line as a fourth server
or a fourth file.

Opened 2026-09-11 by the close of
[R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md).

**What is known.** Both CPU subagent servers now pass `--threads` from the substitution their `cpus`
cap reads, and the constant scan holds that pair by counting the substitution in each of the two
files by name (`scripts/subagentcouplings.py`). The flag gate derives every subagent server the
tree starts from the stack's own wiring and argv, so it would find a third one the day it is
written, but it does not require `--threads` of it. That was decided at the close: the flag gate's
rule runs over both placements of the tier, and the model host's hosted subagent tier is a GPU tier
with no per-tier quota a count could be pinned to, while the right value of the count is the
service's own `cpus` substitution, a relation between two keys of one service that the compose
reader under the flag gate does not read. So a third CPU subagent server written without the pin
would run one thread per hardware thread inside its quota and pass every gate.

**What would close it.** Either a conditional requirement in `flagcheck.py`, holding every compose
server started with `-ngl 0` to a `--threads` that spells the same substitution as its `cpus` key,
which means `composestarts.py` learning to read that key; or the new file's two spellings added to
the CPU budget's constant in the registry, which is the shape the roster file's server took.

## Trail

- 2026-09-11: opened by the close of
  [R-628](628-the-subagent-cpu-servers-thread-count-is-not-pinned-to-its-quota.md), whose origin
  addendum records why the count did not join the flag gate's requirements.
