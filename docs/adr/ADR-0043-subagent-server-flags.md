# ADR-0043: Subagent server flags, checked over the set the stack starts

**Status:** Accepted (2026-09-15)

## Context

Subagents ([ADR-0010](ADR-0010-subagents.md), [ADR-0018](ADR-0018-heterogeneous-subagents.md))
run on `llama-server` processes started in two places: CPU servers written in compose files, and
the model host's subagent tier, whose argv is assembled in Python
([ADR-0030](ADR-0030-brain-handoff.md) and the model host's `config.py`). Each server must start
with flags whose absence crashes nothing. A server without them comes up healthy, passes its
healthcheck, and the only symptom is a slow subagent, one with no tools, or one killed by its
memory cap hours later.

The flags were first checked as search text in the constant registry, one entry per named compose
server. A third server in a new override would have been covered by nothing: a rule applied to a
list someone maintains covers what that person remembered. These decisions were taken under
[ADR-0029](ADR-0029-vision-screen-capture.md), where the registry was then recorded, and moved here
to keep each record to one subject.

## Decision

1. **One rule, `subagentflags.REQUIREMENTS`, enforced by `scripts/flagcheck.py`** in `just check`
   and CI. Every subagent server the tree starts must have:
   - `--jinja`, the model's own chat template, without which llama.cpp's built-in template cannot
     emit a tool call and a subagent with tools silently has none (ADR-0010);
   - the reasoning-off pair, `--chat-template-kwargs '{"enable_thinking": false}'` and
     `--reasoning-budget 0`, one requirement because each flag reaches a different request shape
     the tier serves ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) decision 8 decided
     the pair);
   - `--cache-ram 0`, the host-RAM prompt cache turned off, because its default size equals the
     whole memory cap of a compose subagent server and what it grows into is the mapped weights
     (decided in [ADR-0059](ADR-0059-prompt-cache-per-tier.md));
   - `--threads` on a server started with `-ngl 0`, since llama.cpp otherwise starts one thread per
     hardware thread inside a CPU quota ([ADR-0004](ADR-0004-model-lineup.md) decision 12).

   Requirements are data. A value is checked at every occurrence of its flag, because llama.cpp
   takes the last one written. A requirement may have a `when`, a flag and value an argv must
   already contain for it to apply, which is how one rule reaches a case only part of the set has;
   the condition reads the argv alone, so it reaches a server in a compose file not yet written.
2. **The set of servers is derived, not listed.** `subagentservers.py` counts a compose service as a
   subagent server when the brain's wiring dials it (`CORTEX_SUBAGENTS_ENDPOINT`,
   `CORTEX_SUBAGENTS_GPU_ENDPOINT`, or a `CORTEX_SUBAGENTS_ROSTER__<name>` address whose host is a
   service name) or when its own argv names its model under a `CORTEX_MODEL_FILE_SUBAGENT*`
   variable (`MODEL_PREFIX`). The image does not decide it (the embedder runs the same image), and a
   service declaring no command is not a server here. `composestarts.py` reads what a service is
   started with; `composefiles.py` names the files the compose scans walk.
3. **Both places under one rule.** `hostedtiers.py` adds the model host's subagent tier to the set:
   it resolves the settings field holding a tier's `model_path` to its `validation_alias` and asks
   the same prefix question, since a tier's logical id is what a deployment renames. It reads the
   argv out of `llama_server_argv`'s own return tuple (which contains `_JINJA`) with the tier's
   `extra` (the sidecar's `_SUBAGENT_TAIL`) spliced in, and checks that argv against the rule like
   any compose server's, so a flag renamed on either side fails. It parses with `ast` and never
   imports the brain. A builder returning more than one tuple, or splatting `extra` more than once,
   is refused; an item it cannot reduce becomes `UNREADABLE` rather than being dropped; a subagent
   tier's own tail it cannot read raises. The model host's suite keeps its exact argv assertions
   beside this.
4. **Every model artifact is named under `CORTEX_MODEL_FILE_`** (`FAMILY_PREFIX`), with the word
   after the prefix naming the tier: `CORTEX_MODEL_FILE_EMBED` for the CPU embedder,
   `CORTEX_MODEL_FILE_CORTEX_MMPROJ` for the cortex's projector. Membership in decision 2 rests on
   that convention, so `artifactnames.py` finds the set structurally and checks each member against
   the prefix: in compose, the item after either of `ARTIFACT_FLAGS` (`--model`, `--mmproj`), read
   for the variables it uses; in the model host's settings, every field handed to the resolver
   `_path` that joins a file onto `models_root`. A settings method other than the resolver reading
   `models_root` is refused by name, and a resolver handed no field fails (`MIN_RESOLVED`). The
   short `-m` form is not read (`python -m` uses it), and an item using no variable names nothing to
   check. The naming rule runs inside `flagcheck.py` as the flag rule's precondition, not as a scan
   of its own.
5. **Minimums.** A rule requiring no flag (`MIN_FLAGS`) and a tree starting no subagent server
   (`MIN_SERVERS`) each fail. The success line states the servers, the files starting them, the
   flags required and the artifacts named ([ADR-0042](ADR-0042-cross-tree-constant-registry.md)
   decision 19).
6. **The registry keeps the budget's value, not the rule.** The reasoning-off count is the model
   host's `_NO_REASONING_BUDGET`, compared by the constant registry with the rule's text and with
   the subagent runbook's hand-started `docker run`, so the tier the model host runs and the compose
   servers cannot disagree about it. Which flags must appear together belongs to this rule.

## Consequences

- An override that adds a subagent server is checked the day it is written, and a renamed artifact
  variable outside the family is reported, not skipped. A misnamed projector shows up as vision
  leaving the tool list, which the vision runbook names first.
- A new requirement reaches both places at once, and a brain unit test needs no second copy.
- Not checked, each recorded under `docs/refinements/tasks/`: a server started outside compose (the
  runbook's `docker run`, whose template argument no search text can cover yet, since the
  argument's only declaration sits inside the model host's mixed `_SUBAGENT_TAIL` tuple, which the
  registry cannot reduce); engine file flags other than `--model` and `--mmproj` (`--model-draft`,
  `--lora`); narrowing the resolver refusal; a family member naming a subagent without saying so
  (`CORTEX_MODEL_FILE_HELPER`); a second Python module naming an artifact.

## Alternatives rejected

- **A roster.** A roster compares a page with a set; here the claim is a property of each member
  and the other side is a rule.
- **Per-file search text in the registry**, the first form: a server outside the named files passed.
- **A set closed over the family prefix**: the misspelling it exists to catch sits outside the
  family, so the check would be circular.
- **A free word for the kind** (`CORTEX_<kind>_MODEL_FILE_<tier>`): it admits
  `CORTEX_SUBAGENT_MODEL_FILE_CPU`.
- **Reading settings fields by a `_file` suffix**: replaced by the resolver, which is what really
  joins a file onto the mount.
- **Excluding `--embeddings` servers**: it decided membership in the naming rule's place and let a
  second non-chat server pass silently.
- **A compose shim for the embedder's old variable name**: a nested default is refused by
  `composedefaults.py`, and nothing off this machine reads the key.
- **A requirement restated in a model-host unit test**: a repo-wide deployment invariant would live
  half in each toolchain.

## Related

- Code: `scripts/flagcheck.py`, `subagentflags.py`, `subagentservers.py`, `hostedtiers.py`,
  `composestarts.py`, `moduleconstants.py`, `artifactnames.py`; model host `config.py` and
  `tiers.py`.
- The [repo checks module doc](../modules/repo-gates.md),
  [runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md),
  [runbooks/vision.md](../runbooks/vision.md).
- [ADR-0004](ADR-0004-model-lineup.md), [ADR-0005](ADR-0005-llamacpp-engine.md),
  [ADR-0010](ADR-0010-subagents.md), [ADR-0059](ADR-0059-prompt-cache-per-tier.md),
  [ADR-0042](ADR-0042-cross-tree-constant-registry.md).
