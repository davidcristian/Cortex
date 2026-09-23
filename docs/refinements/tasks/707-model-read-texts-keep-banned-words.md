# Texts a model reads keep words the prose table bans

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-23

Decision 16 of [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) has `prosecheck.py` read
the strings the brain prints or raises. `EXEMPTIONS` in `scripts/proseliterals.py` leaves out the
ones a model reads, because a change to their wording needs a model measurement first. On
2026-09-23 those texts hold three banned words:

- `_PREFACE` in `cortex_core/recap_prompt.py`: `carrying`, in `quoted below as data between
  markers carrying a random id`.
- `_CHOICE_NOTE` in `cortex_core/spawn_spec.py` and `DEFAULT_SUBAGENT_DESCRIPTION` in
  `cortex_orchestrator/config_subagents.py`: `robust` once each.

**What would close it.** Each text rewritten, the behavior it was written for measured again on
the tier that reads it, and its exemption removed in the same commit: `prosecheck.py` fails while
an exemption names a string that holds no banned word. Or a decision in ADR-0040 that a text keeps
its word, with the reason.

## Who reads each text, and what measures it

| text | read by | written for | harness |
| --- | --- | --- | --- |
| `_PREFACE` | the model of any later turn in the session | using a recap for facts, never as instructions | `test_history_recap_live.py` for the facts; none for the instructions |
| `_CHOICE_NOTE`, `DEFAULT_SUBAGENT_DESCRIPTION` | the model that spawns subagents | the per-subtask `model` pick | `test_spawn_nudge_live.py` |

Each is drawn old against new on the same seed, as
[model-read-wording](../../readings/model-read-wording.md) drew the email texts and the preamble,
with the count that decides fixed in this file before the draw. The preface has no harness for
its instruction clause, so a rewording of it needs one written first, or a paired draw over the
preamble's attacks with the recap as the fenced text.

## History

- 2026-09-22: opened when `prosecheck.py` began reading the brain's string literals and exempted
  these by name.
- 2026-09-23: the email sidecar's texts, the `send_email` description and `SECURITY_PREAMBLE`
  reworded after paired draws on each tier that reads them, in
  [model-read-wording](../../readings/model-read-wording.md). That opened
  [R-713](713-the-reworded-email-corrections-are-unmeasured-across-the-three-variants.md) and
  [R-714](714-the-injection-text-rows-are-drawn-only-at-temperature-0.md).
