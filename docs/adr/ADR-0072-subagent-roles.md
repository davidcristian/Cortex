# ADR-0072: Subagent roles name the form of a delegated reply

**Status:** Accepted (2026-09-28)

## Context

A delegated subtask is a free instruction. Each `spawn_subagents` item is `instruction`, `context`
and an optional `model` ([ADR-0018](ADR-0018-heterogeneous-subagents.md) decision 1), so the cortex
has no way to say what kind of subtask it is, and the wording that tells a subagent what form its
reply takes is written again by the cortex on every spawn, or left out.

That wording is the part of a subtask the readings show matters. Under the reply envelope, a
summarization delivered 10 of 40 with no sentence and 39 of 40 when the subtask named what the
reply must contain, and the genre wording "the summary itself" read 30 of 32 beside 29 of 32 for the
generic one ([reply envelope](../readings/reply-envelope.md)). The shipped `REPLY_INSTRUCTION` is one
wording for every subtask ([ADR-0028](ADR-0028-grammar-constrained-subagents.md)), and a hand
review of one tier's replies found an extraction answered as prose, one reply of 96
([R-639](../refinements/tasks/639-the-envelope-judges-read-no-form.md)). The measured subtask kinds
are three: a summarization, an extraction, and a lookup that names one fact the text states (`JUDGES`
in `scripts/envelopejudges.py`).

## Decision

1. **A role is a pure core value with two fields** (`cortex_core/roles.py`).
   `SubagentRole(description, instruction)` is one role and `SubagentRoles(entries)` maps names to
   roles; an entry with an empty name or description fails construction.
   - `instruction` is one sentence the subagent reads after the subtask's own instruction, naming the
     form its reply takes, or empty for a role whose sentence lowered delivery, which leaves the
     subtask's instruction as the cortex wrote it. It goes in the user message, which is where the measured wordings went,
     and ahead of `REPLY_INSTRUCTION` on a constrained run. It is not a system message: no reading
     measured one, and it would lengthen the leading run of system messages the adapter must probe
     and join ([ADR-0071](ADR-0071-leading-system-messages.md)).
   - `description` is what the spawn spec tells the cortex the role returns.

2. **The spawn item gains `role`.** An item is a bare string or `{instruction, model?, context?,
   role?}`. `build_spawn_spec` adds a `role` enum listing each role with its description, and a
   note with an inline object example, for the reason the model choice has one: a cortex given only
   prose folded its pick into the instruction text (ADR-0018 decision 8). The property is offered
   whether or not subagents hold tools, because a role never changes the model. An unknown role or
   one that is not a string is an `is_error` result the cortex can correct.

3. **The task record holds the role's name, and the runner resolves it from the store.**
   `SubagentTask.role` is the name, `""` for none, and `RedisTaskStore` encodes and decodes it
   strictly, as it does `model`. `SubagentRunner` resolves it right after `SubagentRoster.resolve`:
   `SubagentRoles.resolve` returns the role, `NO_ROLE` for `""`, or `None` for a name that is not an
   entry, which the runner persists as an `ok=False` "unknown subagent role" result that keeps the
   task's taint. A role survives a restart or a model swap as a name, and the sentence it stands for
   is rebuilt from code on the next run.

4. **A role cannot relax the taint boundary.** `SubagentRoster.resolve` never receives the role, so
   which model runs is decided exactly as [ADR-0017](ADR-0017-subagent-model-safety.md) states. A
   role holds no model, no tools and no schema. Its sentence is text the brain wrote, so it is
   trusted, and a tainted task's context stays fenced ahead of the instruction
   ([ADR-0013](ADR-0013-untrusted-content.md) decision 3).

5. **What a role does not fix, and why.**
   - **A model preference.** A role would have to name a roster entry, and entries are deployment
     config. The rates also do not rank the models by kind: under the shipped wording the default
     delivered an every-detail summary 28 of 32 times and Qwen3.5-2B 15, while on a figures-keeping
     summary the 2B read 31 and the default 26. Those are one engine image's readings, which ADR-0018
     decision 10 already declined to write into a profile. The cortex keeps picking the model per
     item.
   - **A tool allowlist.** Tools are one dispatcher per wiring, and a tools-enabled wiring is what
     forces the default model. A role narrowing that set would still resolve as tools-enabled, so it
     changes nothing about safety, and no shipped role needs fewer tools.
   - **An output contract the runner checks.** The one machine check of form measured, a tier
     judging its own reply, met the bar written for it on no pick, and a per-task schema waits for a
     structured result ([R-070](../refinements/tasks/070-per-task-caller-schema.md)).

6. **Three roles ship, one per measured kind** (`SHIPPED_ROLES`), and `CORTEX_SUBAGENTS_ROLES`
   (default `true`) turns them off, which restores the spawn spec the ADR-0018 uptake was measured
   against.

   | Name | The reply | Measured shape it follows |
   | --- | --- | --- |
   | `precis` | the whole text made shorter, keeping its figures, names and dates | "Summarize the report below, keeping its figures" |
   | `excerpt` | a list of every item of one kind, as the text writes it, rather than one fact | "Extract every number from the report below" |
   | `answer` | the one fact a question asks for, or that the text does not state it | "What reporting period does the report below cover" |

   `excerpt` and `precis` have no sentence: the cortex names each by its description, and each
   sentence drawn for them lowered its shape's delivery (Consequences).

7. **The names are a proposal for the maintainer's pick.** Roles are a family, so the naming rule in
   `AGENTS.md` applies. Three sets were drawn up:
   - **Recommended: `precis`, `excerpt`, `answer`.** Nouns for the text a subagent returns, ordered
     from the most of the given text a reply keeps to the least: all of it made shorter, the parts
     asked for, one fact. A noun names what a role fixes, the reply's form, and each is an ordinary
     word a model reads without the description.
   - **`summarize`, `extract`, `lookup`.** The verbs of the measured instructions. Literal, but
     `lookup` reads as a fetch, which a tool-less subagent cannot do, and a verb reads as the
     instruction itself.
   - **`abridge`, `transcribe`, `cite`.** One metaphor, a copyist's work, ordered the same way. The
     cortex would have to decode each through its description.

   None collides with an existing family (Mull, Muse, Hunch, Tangent; Still, Lucid, Reverie, Trance;
   Face and Chords) or a backticked identifier; `digest` was left out because it is a field
   `GET /props` returns. Nothing beyond this machine stores a role name: a task record expires after
   an hour and no setting is derived from one, so a rename is an edit to the keys in `roles.py` and
   to the tests and documents that name them.

## Consequences

- The cortex can name a role per subtask, and for a role with a sentence a subagent reads a form
  sentence written once in the brain rather than whatever the cortex wrote that turn.
- On the default pick, drawn on CPU, the `excerpt` and `answer` sentences are not shown to change
  delivery: 26 and 30 of 32 against 30 and 31 without them, each inside the other's interval
  ([role sentences](../readings/role-sentences.md)). The `answer` sentence stays as a form the
  cortex can name.
- On that pick the first `precis` sentence, "Reply with the text you were given made shorter,
  keeping every figure, name and date it states and adding nothing it does not state.", lowered the
  figures-keeping summarization on both conditions drawn: 13 of 32 against 25 without it on CPU, and
  12 of 32 against 27 on the card (build `b10680-d7bd3bfca`, the compose argv at `-ngl 99`, SM clock
  0.73 of its maximum at the median), the intervals apart each time, with 6 and 7 copies of
  the body and 13 cap refusals each. A rewording, "Reply with a shorter version that keeps every
  figure, name and date and adds nothing the text does not state.", does not name the given text as
  the reply, which `REPLY_INSTRUCTION` then forbids. On the card, in one server session with a plain
  cell at the same seeds, it read 20 of 32 against 27 at seeds 1 to 8 and 16 of 32 against 23 at
  seeds 9 to 16, the intervals overlapping each time, and 32 of 64 against 44 at seeds 17 to 32
  (SM clock 0.73 of its maximum at each median). The rule written before that third row, Fisher's
  exact test below p = 0.05 with the sentence lower, gave p = 0.047, so `precis` has no sentence and
  the subtask's own instruction sets the form. Most of the runs the rewording loses are the body
  handed back `ok=True`: 13 copies against 1 plain at seeds 17 to 32
  ([role sentences](../readings/role-sentences.md)).
- On Qwen3.5-2B, the roster alternate, drawn on the card (build `b10680-d7bd3bfca`, the
  `llama-subagent-qwen` argv at `-ngl 99`, SM clock 0.67 of its maximum at the median
  on both seed bases), the `excerpt` sentence lowered the extraction: 10 of 32 against 27
  at seeds 1 to 8 and 8 of 32 against 22 at seeds 9 to 16, apart from the plain cell both times, so
  by the rule written before the second row the drop replicates. The runs it loses mostly write the
  instructions back or stop at the cap repeating numbers. The `precis` rewording read 17 of 32
  against 31 at seeds 1 to 8, apart, and 23 against 27 at seeds 9 to 16, inside; the first `precis`
  sentence read 9. The `answer` sentence read 30 of 32 against 24, inside the plain interval
  ([role sentences](../readings/role-sentences.md)). Neither the
  `excerpt` sentence nor the `precis` rewording is shown to help on either model, so each role has
  none, rather than a sentence chosen per model, which would key a role to roster entries
  (decision 5).
- The cortex pick names a role on every item it delegates. Under the first `excerpt` description,
  "each item the subtask asks for, written exactly as the text writes it", with `spawn_subagents` the
  only tool, every extraction named `answer` and none `excerpt`: 8 of 8 on CPU, 8 of 8 on a second
  wording ("Extract every number"), and 16 of 16 on the card, while the summaries and the lookups
  named their own role ([spawn spec uptake](../readings/spawn-spec-uptake.md)). The shipped
  description names a list of every item of one kind rather than one fact. It drew `excerpt` 7 of 8
  on CPU, and on the card (build `b10680-d7bd3bfca`, the cortex tier's argv at `-ngl 99`, SM clock
  0.62 of its maximum at the median) the extractions named `excerpt` 29 of 32 and `answer` 2,
  while the summaries named `precis` 15 of 16 and the lookups `answer` 16 of 16. That meets the rule
  written before the card row, so the description ships. The names stay a proposal (decision 7).
- The `excerpt` sentence asked for items as the text writes them, and `REPLY_INSTRUCTION` forbids
  repeating the input back. No extraction copied the body on the default pick, with it or without
  it; on the alternate 3 of 32 did with it at seeds 9 to 16, and none without it. With no sentence
  on the role the two no longer meet.
- The per-role escape hatch of ADR-0017
  ([125](../refinements/tasks/125-per-role-escape-hatch.md)) still has no consumer: a role holds no
  model to override.

## Alternatives rejected

- **The sentence as a system message**: decision 1.
- **The sentence stored on the task instead of the name**: the record would keep text a code change
  had replaced, where a name that is gone fails closed.
- **Roles inside `SubagentRoster`**: the roster is models and their resources, and holding roles
  there would put them beside the one function that must never read them.
- **Roles defined in the environment** (`CORTEX_SUBAGENTS_ROLE__<name>`): an operator's sentence
  would be unmeasured text read on every spawn naming it, and the shipped roles cover the measured
  kinds.

## Related

- [ADR-0018](ADR-0018-heterogeneous-subagents.md), [ADR-0017](ADR-0017-subagent-model-safety.md),
  [ADR-0028](ADR-0028-grammar-constrained-subagents.md),
  [ADR-0071](ADR-0071-leading-system-messages.md).
- [brain-core-subagents](../modules/brain-core-subagents.md),
  [brain-core-tools](../modules/brain-core-tools.md), [reply envelope](../readings/reply-envelope.md),
  [role sentences](../readings/role-sentences.md).
