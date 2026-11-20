# No handoff has run through the brain on Qwen3.8-27B

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-20

ADR-0004 decision 8 names `Qwen3.8-27B-UD-Q4_K_M` as the deep pick. Every handoff the readings
record ran on gemma-4-31B: the swap rows ([model swap](../../readings/model-swap.md)) and the
handoff on compose defaults of 2026-11-20
([readings](../../readings/kv-cache-deep-whole.md#a-handoff-on-compose-defaults)). On Qwen3.8-27B
the model host started the deep tier alone and answered one request
([R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md), 2026-11-18). No
turn has gone from the cortex to this model and back with its state read from the store.

The model differs from gemma-4-31B where a handoff reads it. Its template merges the deep
phase's three leading system messages and writes empty thoughts before earlier replies
([deep candidates](../../readings/deep-candidates.md)). It runs at the effort `xhigh`
([R-738](738-the-deep-tier-cannot-set-a-templates-reasoning-effort-or-preserve-flag.md)). Its
load and its first token were read against the swap and stall bounds on 2026-09-26, at an
8192 context.

## What to run

The brain, Redis and the model host from the repo's compose files, as the
[model swap runbook](../../runbooks/model-swap.md#bringing-the-real-host-up) describes:
`CORTEX_ESCALATION=1`, `CORTEX_MODELHOST_BACKEND=supervisor`,
`CORTEX_MODEL_FILE_BRAIN=unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` and a measured
`CORTEX_SWAP_BRAIN_VRAM_MIB`. Run it once with no drafter and once with
`CORTEX_MODEL_FILE_BRAIN_DRAFT` naming the same file. The handoff of 2026-11-20 used
`~/.cache/cortex-run/2026-11-20/a2/live.sh`, which runs this with the file changed.

One chat of three turns: a code word to keep, a task the cortex hands over with
`escalate_to_brain`, and a question about both. Record:

- while the deep tier serves: the cortex `stopped`, the deep server's argv, and the session's
  messages, `cortex:handoff:active` and the handoff's own key in Redis;
- after it: the deep reply in the chat, the deep tier `stopped`, a new cortex process `ready`,
  the third turn answered with the code word and the deep model's explanation, every message in
  the session's list, and both handoff keys gone;
- the card's highest reading above its floor, the load as a share of
  `CORTEX_SWAP_LOAD_TIMEOUT_S`, and the first token as a share of the stall bound.

What would close it: the handoff recorded in a readings file with those items, and any defect it
shows filed.

## History

- 2026-11-20: filed when the maintainer made Qwen3.8-27B the deep pick. The handoff of that day
  ran on gemma-4-31B.
