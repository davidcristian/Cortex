# The set a subagent server joins is a naming convention nothing enforces

**Status:** landed 2026-08-29
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-28 by the close of
[R-467](467-the-hosted-subagent-tier-meets-the-flag-rule-by-hand.md), which brought the model
host's own hosted tier under the flag rule and made both readers decide membership the same way.

`flagcheck.py` runs one rule over two sets, and both sets answer "is this a subagent server" out
of `subagentservers.MODEL_PREFIX`, the string `CORTEX_MODEL_FILE_SUBAGENT`. A compose service is
one when its command spends a variable beginning that way; a hosted tier is one when the settings
field carrying its `model_path` is aliased to a variable beginning that way. Three settings obey
the convention today and the readers are right about all three.

**Nothing holds a fourth to it.** A subagent artifact named `CORTEX_SUBAGENT_MODEL_FILE_CPU`, or
`CORTEX_MODEL_SUBAGENT_FILE_CPU`, is the same artifact under a variable neither reader looks at,
so the server or tier it names falls out of both sets with nothing reported and no gate failing. The gate's
promise is that a server added tomorrow is held the day it is written; that promise rests on the
author of the day spelling one variable the way three earlier ones were spelled, which is exactly
the kind of thing this repo does not leave to memory anywhere else. The wiring reading is the
safety net on the compose side and it has its own hole, an override that leaves a server's
address to the host environment. The hosted side has no second reading at all.

**Why it was left.** The close it came out of had a Python reader to build and a rule to join it
to, and this is a different question: not "what does this declaration say" but "is every
declaration of this kind spelled so that it can be found". Answering it means enumerating the
artifact settings this tree writes, in two languages, and deciding for each whether it names a
subagent's model, which is a judgement the current readers get for free from the prefix and would
have to make some other way.

**What would close it.** The likeliest shape is a check that the `CORTEX_MODEL_FILE_*` family is
closed: every variable in it that this tree spells, in a compose command or a settings alias, is
classified by one of the readers, and a new one that no reader claims is reported rather than
ignored. That turns an unreported miss into a failure at the moment the variable is written, without
anybody having to guess which artifacts are a subagent's. The alternative is to argue that the
prefix belongs in the constant registry as a value the settings must spell, which holds the
spelling of the ones already written down and not the arrival of one that is not.

## Trail

- 2026-08-28: opened by the close of
  [R-467](467-the-hosted-subagent-tier-meets-the-flag-rule-by-hand.md), which gave the hosted
  tier the same membership reading the compose side already used and left the reading itself
  resting on a convention.
- 2026-08-29: landed as the
  [ADR-0029 addendum on holding the naming a derived set is read out of](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-29-the-naming-a-derived-set-is-read-out-of-is-held-and-structurally),
  a second rule in the same scan: `scripts/artifactnames.py` returns every model artifact this
  tree names and `scripts/flagcheck.py` holds each to beginning `CORTEX_MODEL_FILE_`.
  **Re-derivation mutated both placements against the committed gate first**, and the entry was
  right where it mattered and generous nowhere: respelling the sidecar's alias out of the family
  and deleting that tier's reasoning-off tail printed `flagcheck OK: the 2 subagent server(s)`
  and exited 0. What already holds the three settings written down was found and is not this: the
  model_manager suite pins all three aliases through the environment it sets, so renaming one
  fails the brain suite, while nothing at all says anything about a fourth arriving.
  **The entry's own preferred shape was rejected as circular.** Holding the `CORTEX_MODEL_FILE_*`
  family closed makes the rule's domain the prefix whose observance it checks, so
  `CORTEX_SUBAGENT_MODEL_FILE_CPU` is outside it by construction and the gate could not fail for
  the fault it was built for; the mutation narrowing the domain that way makes exactly the three
  checks that respell a name fail. So the artifacts are found structurally instead, the item after
  llama.cpp's own `--model` and the settings field a tier reads its `model_path` from, which pays
  the cost this entry named by not making the judgement at all: the structural reading enumerates
  and the prefix still judges. **The registry alternative was declined on the evidence**, since it
  holds the spelling of the three the brain suite already holds and says nothing about the fourth.
  Three exclusions are deliberate and argued: the short spelling of the model flag, an item
  spending no variable, and an argv declaring `--embeddings`. That last one leaves a live
  counterexample in the tree, which is what the close opened,
  [R-492](492-the-embedder-names-its-artifact-outside-the-family.md).
