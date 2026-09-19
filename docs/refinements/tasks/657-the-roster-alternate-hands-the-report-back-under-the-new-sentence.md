# The roster alternate hands the report back under the new sentence too

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** a deployment runs the roster alternate, as the `qwen` entry the roster overlay adds or
as the default `CORTEX_MODEL_FILE_SUBAGENT` names, and a delegated summarization comes back as the
report body it was given.
**Verified:** 2026-09-19

Opened 2026-09-13 by the close of
[R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md), which reworded
`REPLY_INSTRUCTION` so it names the input as well as the answer. That wording removes the copy on
the default pick, 14 of 32 to none, and it does not remove it on the roster alternate: on the
sentence-change addendum's samples Qwen3.5-2B still hands the report body back 16 times in 32 on the
summarization that asks for every detail, against 27 under the old wording and 7 under the envelope
alone. Over the four shapes the same addendum declares, the alternate reads 97 of 128 under the new
wording and 99 under no sentence at all, and on the fourth shape it hands the report body back once
in 32, where the summarization asking for every detail hands it back 16 times. So the sentence costs
two answers in 128 on this pick, and the copy it leaves is concentrated on the harness wording that
asks for every detail.

**What it is not.** It is not the per-entry wording, which is declined
([R-482](482-the-sentence-is-one-wording-for-every-entry.md)): one wording ships to every roster
entry, and the one that ships is the better of the two measured on both picks. It is not an argument
for dropping the sentence either, since the default pick reads 91 of 96 with it and 71 without.

**What would close it.** The remedy
[R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md) named and did not
take: a runner-side refusal of a reply that is the context the runner already holds, handed back.
`scripts/envelopejudges.py` already draws that comparison for a reading, over letters and digits at
nine tenths, so the arithmetic exists and the question is where a refusal belongs and what it costs.
It has to answer the exemption the lapse addendum at the origin names, a subtask that asks for the
body back, and it would be a second reading of a reply rather than a second completion, which is
what makes it cheap where a self-judge is not.

**Why it waits.** The alternate is an opt-in override rather than the shipped entry, and a copy
arrives `ok=True`, so nothing about it is visible until a deployment reads a delegated summary and
finds its own report in it.

## Trail

- 2026-09-13: opened by the close of
  [R-641](641-the-shipped-sentence-hands-the-report-back-on-a-summarization.md), whose seeded
  samples are under `measurements/envelope-sentence-2026-09-13/`, which git ignores, one directory
  per pick.
- 2026-09-19: Re-derived, and the trigger has not fired; it also named only one of the two routes to
  the alternate. The documented route is `docker/docker-compose.subagents-roster.yml`, which adds
  Qwen3.5-2B as roster entry `qwen` under `CORTEX_MODEL_FILE_SUBAGENT_QWEN` beside the gemma-4-E4B
  default, and the cortex picks it per subtask through the spawn tool's `model` property on a
  tool-less, untainted turn, which is where a summarization of text the cortex already holds runs.
  Pointing `CORTEX_MODEL_FILE_SUBAGENT` at it, the only route the trigger named, is the other. The
  trigger now names both. Read with `scripts/envelopefloor.py` over the alternate's samples in that
  directory, the new wording's every-detail summarization stands on 16 of 32 with 16 copies, its
  fourth shape hands the body back once, and its four shapes deliver 31, 15, 27 and 24, the 97 of
  128 above; the 27 under the old wording and 7 under the envelope alone were not re-read.
  `copied` in `scripts/envelopejudges.py` still compares letters and digits at `COPIED = 0.9`, so
  the arithmetic the remedy names is where this entry says, and `REPLY_INSTRUCTION` in
  `subagent_reply.py` is still the wording those samples drew.
