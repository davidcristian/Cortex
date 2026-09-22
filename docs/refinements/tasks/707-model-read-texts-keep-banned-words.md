# Texts a model reads keep words the prose table bans

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md)
**Verified:** 2026-09-22

Decision 16 of [ADR-0040](../../adr/ADR-0040-prose-and-comment-style.md) has `prosecheck.py` read
the strings the brain prints or raises. `EXEMPTIONS` in `scripts/proseliterals.py` leaves out the
ones a model reads, because a change to their wording needs a model measurement first. On
2026-09-22 those strings hold eleven banned words:

- `SECURITY_PREAMBLE` in `cortex_core/untrusted.py`: `carry`, in `The markers carry a random id
  per turn`. This is the injection framing of
  [ADR-0013](../../adr/ADR-0013-untrusted-content.md), and one of its clauses is there because a
  measurement showed a model needs it.
- `_PREFACE` in `cortex_core/recap_prompt.py`: `carrying`.
- `_CHOICE_NOTE` in `cortex_core/spawn_spec.py` and `DEFAULT_SUBAGENT_DESCRIPTION` in
  `cortex_orchestrator/config_subagents.py`: `robust` once each.
- `_FILENAME_HELP`, `SEARCH_REFUSED`, `FOLDER_HELP` and `FOLDER_UNKNOWN` in
  `cortex_email/values.py`: `rides`, `spells`, `carries` and `spelled` twice.
- `SEARCH_REFUSED` and `FOLDER_UNKNOWN` in `cortex_orchestrator/own_texts.py`, which restate the
  email sidecar's texts word for word and which `crosscheck.py` holds equal to them: `spells` and
  `spelled`.

**What would close it.** Each text rewritten, the behavior it was written for measured again on
the tier that reads it, and its exemption removed in the same commit: `prosecheck.py` fails while
an exemption names a string that holds no banned word. Or a decision in ADR-0040 that a text keeps
its word, with the reason.

## History

- 2026-09-22: opened when `prosecheck.py` began reading the brain's string literals and exempted
  these by name.
