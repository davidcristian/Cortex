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
   roles; an entry with an empty name, description or instruction fails construction.
   - `instruction` is one sentence the subagent reads after the subtask's own instruction, naming the
     form its reply takes. It goes in the user message, which is where the measured wordings went,
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
   | `excerpt` | each item the subtask asks for, as the text writes it | "Extract every number from the report below" |
   | `answer` | the one fact a question asks for, or that the text does not state it | "What reporting period does the report below cover" |

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

- The cortex can name a role per subtask, and a subagent reads a form sentence written once in the
  brain rather than whatever the cortex wrote that turn.
- On the default pick, drawn on CPU, the `excerpt` and `answer` sentences are not shown to change
  delivery: 26 and 30 of 32 against 30 and 31 without them, each inside the other's interval
  ([reply envelope](../readings/reply-envelope.md), "The role sentences"). They stay as a form the
  cortex can name.
- On that pick the `precis` sentence delivered the figures-keeping summarization 13 of 32 against
  25 without it, the one cell apart, with 6 copies of the body and 13 cap refusals. It ships
  unchanged until the replication on the card and the Qwen3.5-2B rows
  ([755](../refinements/tasks/755-the-precis-sentence-read-lower-on-one-condition.md)) are drawn.
- The cortex pick names a role on every item it delegates. Drawn on CPU with `spawn_subagents` the
  only tool, 24 invited turns each named one role: `precis` for each summary and `answer` for each
  lookup, 8 of 8 each, and `answer` for each of 8 extractions, never `excerpt`
  ([spawn spec uptake](../readings/spawn-spec-uptake.md)). The property is used, and on extraction
  the names or descriptions mislead the cortex, so such a subtask reads the one-fact sentence. That
  is evidence for the pick of decision 7, and the names ship unchanged until the replication on the
  card ([756](../refinements/tasks/756-the-cortex-names-answer-for-an-extraction.md)) is drawn.
- On a constrained run the `excerpt` sentence asks for items as the text writes them, and
  `REPLY_INSTRUCTION` then forbids repeating the input back. No extraction copied the body with that
  sentence or without it, so the two do not conflict on the default pick.
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
  [brain-core-tools](../modules/brain-core-tools.md),
  [reply envelope](../readings/reply-envelope.md).
